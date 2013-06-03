from unittest import TestLoader, TextTestRunner, TestSuite
#Import all Matcher tests.
from Tribler.Test.TUPT.Matcher.test_MatcherControl import TestMatcherControl
from Tribler.Test.TUPT.Matcher.test_TheMovieDBMatcherPlugin import TestTheMovieDBMatcherPlugin
#Import all Parser tests.
from Tribler.Test.TUPT.Parser.test_ParserControl import TestParserControl
from Tribler.Test.TUPT.Parser.test_IMDbParserPlugin import TestIMDbParserPlugin
#Import all TorrentFinder tests.
from Tribler.Test.TUPT.TorrentFinder.test_KatPhTorrentFinderPlugin import TestKatPhTorrentFinderPlugin
from Tribler.Test.TUPT.TorrentFinder.test_SortedTorrentList import TestSortedTorrentList

if __name__ == "__main__":    
    runner = TextTestRunner(verbosity = 2)
    runner.run()