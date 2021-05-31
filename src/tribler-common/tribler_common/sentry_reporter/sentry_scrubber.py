import re

from tribler_common.sentry_reporter.sentry_reporter import (
    BREADCRUMBS,
    RELEASE,
    VALUES,
)
from tribler_common.sentry_reporter.sentry_tools import delete_item, distinct_by, format_version, modify_value


class SentryScrubber:
    """This class has been created to be responsible for scrubbing all sensitive
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
            'Users',
        ]

        self.dict_keys_for_scrub = ['USERNAME', 'USERDOMAIN']
        self.event_fields_to_cut = []
        self.exclusions = ['local', '127.0.0.1']

        # this is the dict (key: sensitive_info, value: placeholder)
        self.sensitive_occurrences = {}

        # placeholders
        self.create_placeholder = lambda text: f'<{text}>'

        self.placeholder_user = self.create_placeholder('user')
        self.placeholder_ip = self.create_placeholder('IP')
        self.placeholder_hash = self.create_placeholder('hash')

        # compiled regular expressions
        self.re_folders = []
        self.re_ip = None
        self.re_hash = None

        self._compile_re()

    def _compile_re(self):
        """Compile all regular expressions."""
        for folder in self.home_folders:
            folder_pattern = r'(?<=' + folder + r'[/\\])[\w\s~]+(?=[/\\])'
            self.re_folders.append(re.compile(folder_pattern, re.I))

        self.re_ip = re.compile(r'(?<!\.)\b(\d{1,3}\.){3}\d{1,3}\b(?!\.)', re.I)
        self.re_hash = re.compile(r'\b[0-9a-f]{40}\b', re.I)

    def scrub_event(self, event):
        """Main method. Removes all sensitive and unnecessary information.

        Args:
            event: a Sentry event.

        Returns:
            Scrubbed the Sentry event.
        """
        if not event:
            return event

        # remove unnecessary fields
        for field_name in self.event_fields_to_cut:
            delete_item(event, field_name)

        # remove duplicates from breadcrumbs
        # duplicates will be identifiers by the `timestamp` field
        def _remove_duplicates_from_breadcrumbs(breadcrumbs):
            return modify_value(breadcrumbs, VALUES, lambda values: distinct_by(values, 'timestamp'))

        modify_value(event, BREADCRUMBS, _remove_duplicates_from_breadcrumbs)

        # skip dev version
        modify_value(event, RELEASE, format_version)

        # remove sensitive information
        scrubbed_event = self.scrub_entity_recursively(event)

        # this second call is necessary for complete the entities scrubbing
        # which were found at the end of the previous call
        scrubbed_event = self.scrub_entity_recursively(scrubbed_event)

        return scrubbed_event

    def scrub_text(self, text):
        """Replace all sensitive information from `text` by corresponding
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

        def scrub_username(m):
            group = m.group(0)
            if group in self.exclusions:
                return group
            self.add_sensitive_pair(group, self.placeholder_user)
            replacement = self.placeholder_user
            return replacement

        for regex in self.re_folders:
            text = regex.sub(scrub_username, text)

        # cut an IP
        def scrub_ip(m):
            return self.placeholder_ip if m.group(0) not in self.exclusions else m.group(0)

        text = self.re_ip.sub(scrub_ip, text)

        # cut hash
        text = self.re_hash.sub(self.placeholder_hash, text)

        # replace all sensitive occurrences in the whole string
        if self.sensitive_occurrences:
            escaped_sensitive_occurrences = [re.escape(user_name) for user_name in self.sensitive_occurrences]
            pattern = r'([^<]|^)\b(' + '|'.join(escaped_sensitive_occurrences) + r')\b'

            def scrub_value(m):
                if m.group(2) not in self.sensitive_occurrences:
                    return m.group(0)
                return m.group(1) + self.sensitive_occurrences[m.group(2)]

            text = re.sub(pattern, scrub_value, text)

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
            result = {}
            for key, value in entity.items():
                if key in self.dict_keys_for_scrub:
                    placeholder = self.create_placeholder(key)
                    self.add_sensitive_pair(value, placeholder)
                result[key] = self.scrub_entity_recursively(value, depth)
            return result

        return entity

    def add_sensitive_pair(self, text, placeholder):
        if text in self.sensitive_occurrences:
            return

        self.sensitive_occurrences[text] = placeholder
