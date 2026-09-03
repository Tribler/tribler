from __future__ import annotations

import json
import logging
import os
from asyncio import Future, sleep
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from sentencepiece import SentencePieceProcessor, SentencePieceTrainer

from tribler.core.notifier import Notification, Notifier

if TYPE_CHECKING:
    from ipv8.taskmanager import TaskManager

    from tribler.tribler_config import TriblerConfigManager

logger = logging.getLogger(__name__)
LOG_LEVELS = {50: 3, 40: 2, 30: 1, 20: 0, 10: 0, 0: 0}
"""
logging              {50: CRITICAL/FATAL, 40: ERROR, 30: WARNING/WARN, 20: INFO, 10: DEBUG, 0: NOTSET}
SentencePieceTrainer { 3:          FATAL,  2: ERROR,  1:      WARNING,  0: INFO                      }
"""


class AugmentedSearch:
    """
    This class is responsible for "slow" search. It creates its own language, based on torrent titles, to augment
    user queries.
    """

    study_task_name = "Perform self-study of torrent titles"

    def __init__(self, config: TriblerConfigManager, notifier: Notifier, task_manager: TaskManager) -> None:
        """
        We place our trained vocabulary and model into the state directory from the config.
        """
        super().__init__()

        self.config = config
        self.max_title_length = 4192
        self.title_window: list[str] = []
        self.initialized = False
        self.write_completed: Future[None] = Future()
        self.task_manager = task_manager

        # Annoyingly, SentencePiece operates on files. So, we have to take care of all the due diligence.
        self.model_file = Path(config.get_version_state_dir()) / "_m_torrent_titles.model"
        self.title_cache_file = Path(config.get_version_state_dir()) / "_m_torrent_titles.cache.txt"
        if not self.model_file.parent.exists():
            self.model_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.title_cache_file.parent.exists():
            self.title_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.processor: SentencePieceProcessor = (SentencePieceProcessor(model_file=str(self.model_file))
                                                  if self.model_file.exists() else SentencePieceProcessor())
        logger.debug("Loaded vocabulary %s",
                     str([self.processor.IdToPiece(i) for i in range(self.processor.vocab_size())]))

        # Async stuff
        notifier.add(Notification.torrent_metadata_added, self.consume_torrent_metadata)
        self.task_manager.register_shutdown_task(self.on_shutdown)

    def on_shutdown(self) -> None:
        """
        Quickly dump our cache onto the disk.
        """
        with open(str(self.title_cache_file), "w") as f:
            json.dump(self.title_window, f)

    def consume_torrent_metadata(self, metadata: dict) -> None:
        """
        We found a new torrent title. Put it in the cache and start learning when we have sufficient data.
        """
        title = metadata.get("title")
        if title is None:
            return
        # If we had a previous cache, it is not at the flush limit. The only time it could be at the flush limit is
        # when we get new data (right now). So, this is where we check for it. Same holds for writing the file.
        if not self.initialized:
            if self.title_cache_file.exists():
                with open(str(self.title_cache_file)) as f:
                    self.title_window = json.load(f)
            self.initialized = True
        self.title_window.append(title[:self.max_title_length])
        self.schedule_study()

    def schedule_study(self) -> None:
        """
        Check if we should update our vocabulary, either due to new information or because we have no vocabulary.
        """
        if self.task_manager.get_task(AugmentedSearch.study_task_name) is None and len(self.title_window) > 50:
            titles = self.title_window
            self.title_window = []
            logger.info("Scheduling a torrent title vocabulary update.")
            self.task_manager.register_task(AugmentedSearch.study_task_name, self.study, titles)

    def write(self, trained_model: bytes) -> None:
        """
        SentencePiece really wants to write to disk and then load it again. We need to be sure that new input was
        actually written to disk before reading it, or we lose data.
        """
        logger.info("Trained new torrent title vocabulary, writing to disk.")
        with open(self.model_file, "wb") as f:
            f.write(trained_model)

        async def _await_write() -> None:
            await sleep(0.01)
            while not os.access(str(self.model_file), os.R_OK):
                await sleep(0.01)
        self.write_completed = self.task_manager.replace_task("disk flusher", _await_write)

    async def study(self, titles: list[str]) -> None:
        """
        Study our most recent torrent titles and add them to the top tokens that we have already found in the past.
        """
        logger.info("Training torrent title vocabulary with pre-existing vocabulary of size %d",
                    self.processor.vocab_size())
        best_history = []
        for i in sorted((j for j in range(self.processor.vocab_size())), key=self.processor.get_score, reverse=True):
            if i not in [self.processor.bos_id(), self.processor.eos_id(),
                         self.processor.pad_id(), self.processor.unk_id()]:
                best_history.append(self.processor.IdToPiece(i).replace("▁", ""))
                # Our vocabulary can only fit 8000 entries. Allocate 50 new unigrams per new torrent title.
                if len(best_history) == 8000 - 50*len(titles):
                    break
        trainingset = chain(best_history, titles)
        self.write_completed = Future()
        log_level = LOG_LEVELS.get(logger.getEffectiveLevel(), 0)
        SentencePieceTrainer.Train(input_format="text", model_writer=self, model_type="unigram",
                                   sentence_iterator=trainingset, vocab_size=8000, hard_vocab_limit=False,
                                   max_sentence_length=self.max_title_length, minloglevel=log_level)
        self.title_cache_file.unlink(missing_ok=True)
        await self.write_completed
        self.processor.Load(model_file=str(self.model_file))
        logger.info("Training torrent title vocabulary completed, new model of size %d loaded!",
                    self.processor.vocab_size())

    def needs_kickstart(self) -> bool:
        """
        Check if we could use a good seeding.
        """
        return self.processor.vocab_size() == 0

    def to_phrases(self, pieces: list[str]) -> list[list[str]]:
        """
        What we get from SentencePiece is pieces. What we want is the pieces that make up a word, i.e., a phrase.
        Note that each word is separated by "▁" and may span several list elements.
        """
        phrases: list[list[str]] = []
        current_phrase: list[str] = []
        for piece in pieces:
            if piece.startswith("▁"):
                if len(current_phrase) > 0:
                    phrases.append(current_phrase)
                    current_phrase = []
                if piece != "▁":
                    current_phrase += [piece[1:]]
            else:
                current_phrase += [piece]
        if len(current_phrase) > 0:
            phrases.append(current_phrase)
        return phrases

    def augment(self, search: str, limit: int = 1000, offset: int = 1) -> tuple[str, list[str]]:
        """
        Augment the original user search string and create an SQL-injection-safe SQL query and its parameters.
        """
        pieces: list[str] = self.processor.encode(search, out_type=str)
        if len(pieces) == 0:
            return ("title LIKE ?", ["%"])

        phrases = self.to_phrases(pieces)
        conjunction: list[str] = []
        parameters: list[str] = []

        for phrase in phrases:
            # Note: there is no such thing as a zero-length phrase.
            if len(phrase) == 1:
                # Raw conjunction
                parameters.append(f"%{phrase[0]}%")
                conjunction.append("title LIKE ?")
            else:
                # Disjunction
                disjunction_len = 0
                for i in range(len(phrase)):
                    phrase_permutation = ""
                    for j in range(len(phrase)):
                        if i != j and len(phrase) > 1:
                            phrase_permutation += phrase[j] + ("%" if j + 1 == i else "")
                    if phrase_permutation:
                        disjunction_len += 1
                        parameters.append("%" + phrase_permutation + ("" if phrase_permutation.endswith("%") else "%"))
                conjunction.append(f"({' OR '.join(['title LIKE ?'] * disjunction_len)})")

        conjunction_str = " AND ".join(conjunction)
        if len(conjunction_str) <= 2:  # Single item: "()"
            conjunction_str = "title LIKE ?"
            parameters = [f"%{''.join(phrases[0])}%"]
        query = f"SELECT rowid FROM ChannelNode WHERE {conjunction_str} LIMIT {limit} OFFSET {offset}"  # noqa: S608
        logger.debug("Augmented '%s' to '%s', with params %s", search, query, str(parameters))
        return query, parameters
