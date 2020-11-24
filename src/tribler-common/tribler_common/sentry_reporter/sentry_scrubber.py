import re

from tribler_common.sentry_reporter.sentry_reporter import (
    BREADCRUMBS,
    CONTEXTS,
    EXTRA,
    LOGENTRY,
    OS_ENVIRON,
    REPORTER,
    STACKTRACE,
    SYSINFO,
)
from tribler_common.sentry_reporter.sentry_tools import delete_item, modify_value


class SentryScrubber:
    """ This class has been created to be responsible for scrubbing all sensitive
    and unnecessary information from Sentry event.
    """

    def __init__(self):
        # https://en.wikipedia.org/wiki/Home_directory
        self.home_folders = [
            'users',
            'usr',
            'home',
            'u01',
            'var',
            r'data\/media',
            r'WINNT\\Profiles',
            'Documents and Settings',
        ]

        self.event_fields_to_cut = ['modules']

        self.placeholder_user = '<user>'
        self.placeholder_ip = '<IP>'
        self.placeholder_hash = '<hash>'

        self.exclusions = ['local', '127.0.0.1']

        self.user_name = None

        self.re_folders = []
        self.re_ip = None
        self.re_hash = None

        self._compile_re()

    def _compile_re(self):
        """ Compile all regular expressions.
        """
        for folder in self.home_folders:
            folder_pattern = r'(?<=' + folder + r'[/\\])\w+(?=[/\\])'
            self.re_folders.append(re.compile(folder_pattern, re.I))

        self.re_ip = re.compile(r'(?<!\.)\b(\d{1,3}\.){3}\d{1,3}\b(?!\.)', re.I)
        self.re_hash = re.compile(r'\b[0-9a-f]{40}\b', re.I)

    def scrub_event(self, event):
        """ Main method. Removes all sensitive and unnecessary information.

        Args:
            event: a Sentry event.

        Returns:
            Scrubbed the Sentry event.
        """
        if not event:
            return event

        for field_name in self.event_fields_to_cut:
            delete_item(event, field_name)

        modify_value(event, EXTRA, self.scrub_entity_recursively)
        modify_value(event, LOGENTRY, self.scrub_entity_recursively)
        modify_value(event, BREADCRUMBS, self.scrub_entity_recursively)

        reporter = event.get(CONTEXTS, {}).get(REPORTER, None)
        if not reporter:
            return event

        modify_value(reporter, OS_ENVIRON, self.scrub_entity_recursively)
        modify_value(reporter, STACKTRACE, self.scrub_entity_recursively)
        modify_value(reporter, SYSINFO, self.scrub_entity_recursively)

        return event

    def scrub_text(self, text):
        """ Replace all sensitive information from `text` by corresponding
        placeholders.

        Sensitive information:
            * IP
            * User Name
            * 40-symbols-long hash

        A found user name will be stored and used for further replacements.
        Args:
            text:

        Returns:
            The text with removed sensitive information.
        """
        if text is None:
            return text

        def cut_username(m):
            group = m.group(0)
            if group in self.exclusions:
                return group
            self.user_name = group
            replacement = self.placeholder_user
            return replacement

        for regex in self.re_folders:
            text = regex.sub(cut_username, text)

        # cut an IP
        def cut_ip(m):
            return self.placeholder_ip if m.group(0) not in self.exclusions else m.group(0)

        text = self.re_ip.sub(cut_ip, text)

        # cut hash
        text = self.re_hash.sub(self.placeholder_hash, text)

        # replace all user name occurrences in the whole string
        if self.user_name:
            text = re.sub(r'\b' + re.escape(self.user_name) + r'\b', self.placeholder_user, text)

        return text

    def scrub_entity_recursively(self, entity, depth=10):
        """Recursively traverses entity and remove all sensitive information.

        Can work with:
            1. Text
            2. Dictionaries
            3. Lists

        All other fields just will be skipped.

        Args:
            entity: an entity to process.
            depth: depth of recursion.

        Returns:
            The entity with removed sensitive information.
        """
        if depth < 0 or not entity:
            return entity

        depth -= 1

        if isinstance(entity, str):
            return self.scrub_text(entity)

        if isinstance(entity, list):
            return [self.scrub_entity_recursively(item, depth) for item in entity]

        if isinstance(entity, dict):
            return dict((key, self.scrub_entity_recursively(entity[key], depth)) for key in entity)

        return entity
