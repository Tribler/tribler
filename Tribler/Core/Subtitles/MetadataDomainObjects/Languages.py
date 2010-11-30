# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
import csv
import codecs

MAX_SUPPORTED_LANGS = 32

DEFAULT_LANG_CONF_FILE = "res/subs_languages.csv"


def _loadLanguages(langFilePath):
    """
    Read a list of languages from a csv file
    
    Reads a list of language codes and the relative language
    description from a csv text file. On each line of the file
    there must be a couple of ISO 693-2 formatted language code
    'code' and the textual description for the language.
    e.g. ita, Italian
    """
    languages = {}
    with codecs.open(langFilePath, "r","utf-8") as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            # Must be exactly two entries code, description
            if len(row) != 2 :
                raise ValueError("Erroneous format in csv")
            # Only check if the code is a three character code, not
            # if it is really a valid ISO 639-2 Cod
            if len(row[0]) != 3 :
                raise ValueError("Lang codes must be 3 characters length")
                
            languages[row[0]] = row[1]
    
    return languages

_languages = {
    'ara':'Arabic',
    'ben':'Bengali',
    'ces':'Czech',
    'dan':'Danish',
    'deu':'German',
    'ell':'Greek',
    'eng':'English',
    'fas':'Persian',
    'fin':'Finnish',
    'fra':'French',
    'hin':'Hindi',
    'hrv':'Croatian',
    'hun':'Hungarian',
    'ita':'Italian',
    'jav':'Javanese',
    'jpn':'Japanese',
    'kor':'Korean',
    'lit':'Latvia',
    'msa':'Malay',
    'nld':'Dutch',
    'pan':'Panjabi',
    'pol':'Polish',
    'por':'Portuguese',
    'ron':'Romanian',
    'rus':'Russian',
    'spa':'Spanish',
    'srp':'Serbian',
    'swe':'Swedish',
    'tur':'Turkish',
    'ukr':'Ukranian',
    'vie':'Vietnamese',
    'zho':'Chinese'
}
assert len(_languages) <= 32, "May not contain more than 32 entries, since we use 32 bits as a language mask"


class Languages(object):
    '''
    Performs the translation between supported languages and bitstrings.
    '''
            
    def __init__(self, lang_dict=_languages):
        '''
        Constructor
        '''
        
        # Contains paris of the type { lang_code : Long language Name}
        # its values are read from a file
        self.supportedLanguages = {}
        
        # for each language code defined in supportedLanguages
        # maps contains the bit string representing that language
        self.langMappings = {}
        
        self.supportedLanguages = lang_dict
        
        self._supportedCodes = frozenset(self.supportedLanguages.keys())
        
        if len(self.supportedLanguages) > MAX_SUPPORTED_LANGS:
            raise ValueError("Maximum number of supported languages is %d" %
                             MAX_SUPPORTED_LANGS)
            
        self._initMappings()                


    def _initMappings(self):
        """
        Assigns bitmasks to languages.
        
        Assigns bitmasks to language codes. Language codes are sorted
        lexicographically and the first bitmask (i.e. 0x1) is given to
        the first code in this order.
        """
        counter = 0
        sortedKeys = sorted(self.supportedLanguages.keys())
        for code in sortedKeys:
            self.langMappings[code] = 1 << counter
            counter += 1
        
        
            
    def getMaskLength(self):
        """
        Returns the length of the languages bit mask.
        
        Returns the necessary length to contain the language bit mask
        for the languages represented by this instance.
        It is always a power of two, even if less bits would actually be
        required
        """
        
        # always returnes the maximum number of supported languages
        return MAX_SUPPORTED_LANGS
    

    
    def maskToLangCodes(self, mask):
        """
        Given a int bitmask returns the list of languages it represents.
        
        Translates the bitmask passed in as parameters into a list
        of language codes that represent that bitmask.
        
        @param mask: a bitmask representing languages (integer)
        @return: a list of language codes string
        @precondition: mask < 2**32 -1

        """
        assert mask < 2**32 , "Mask mast be a 32 bit value"
        assert mask >=0 , "Mask must  be positive"
        codeslist = []
        
        for code, cur_mask in self.langMappings.iteritems():
            if mask & cur_mask != 0 :
                codeslist.append(code)
        
        return sorted(codeslist)
    
    
    
    def langCodesToMask(self, codes):
        """
        Given a list of languages returns the bitmask representing it.
        
        Translates a list of language codes in a bitmask representing it.
        Converse operation of masktoLangCodes.
        
        @param codes: a list of language codes. That code must be one of the
                      keys of self.supportedLanguages.keys()
        """
        
        validCodes = self.supportedLanguages.keys()
        
        #mask is the integer value of the bitfield
        mask = 0
        for lang in codes:
            #precondition: every entry in codes is contained in 
            #self.supportedLanguages.keys
            if lang not in validCodes:
                raise ValueError(lang + " is not a supported language code")
            mask = mask | self.langMappings[lang]
        
        return mask
    
    
    def isLangCodeSupported(self, langCode):
        """
        Checks whether a given language code is supported.
        
        Returns true if the language code is one of the supported languages
        for subtitles
        """
        return langCode in self._supportedCodes
    
    def isLangListSupported(self, listOfLangCodes):
        """
        Checks whether a list of language codes is fully supported.
        
        Returns true only if every entry in the list passed in as parameter
        is supported as a language for subtitles.
        """
        givenCodes = set(listOfLangCodes)
        return givenCodes & self._supportedCodes == givenCodes
    
    
    def getLangSupported(self):
        return self.supportedLanguages
            

class LanguagesProvider(object):
    
    _langInstance = None
        
    @staticmethod
    def getLanguagesInstance():
        if LanguagesProvider._langInstance is None:
            #lang_dict = _loadLanguages(DEFAULT_LANG_CONF_FILE)
            LanguagesProvider._langInstance = Languages(_languages)    
        return LanguagesProvider._langInstance
    
    
