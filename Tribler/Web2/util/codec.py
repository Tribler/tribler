
#------------- ENCODING OF HTTP GET PARAMETERS ----------------

# unreserved ascii values for URLs (RFC 2396)
             # -   _   .   !    ~   *   '   (   )
unreserved = [45, 95, 46, 33, 126, 42, 39, 40, 41]
unreserved.extend(range(97, 123)) # a-z
unreserved.extend(range(65, 91))  # A-Z
unreserved.extend(range(48, 58))  # 0-9


# encoding of GET parameters in URLs
def encodehttpget(str):
    utf8enc = str.encode("utf-8")

    encoded = ""

    for c in utf8enc:
        if ord(c) in unreserved:
            encoded = encoded + c
        else:
            encoded = encoded + "%"
            encoded = encoded + hex(ord(c))[2:]

    return encoded

#------------- DECODING OF HTML CHARACTER ENTITY REFERENCES ----------------

#list taken from http://www.w3.org/TR/1999/REC-html401-19991224/sgml/entities.html
htmlchars = {}
htmlchars["nbsp"] =   160 
htmlchars["iexcl"] =  161 
htmlchars["cent"] =   162 
htmlchars["pound"] =  163 
htmlchars["curren"] = 164 
htmlchars["yen"] =    165 
htmlchars["brvbar"] = 166 
htmlchars["sect"] =   167 
htmlchars["uml"] =    168 
htmlchars["copy"] =   169 
htmlchars["ordf"] =   170 
htmlchars["laquo"] =  171 
htmlchars["not"] =    172 
htmlchars["shy"] =    173 
htmlchars["reg"] =    174 
htmlchars["macr"] =   175 
htmlchars["deg"] =    176 
htmlchars["plusmn"] = 177 
htmlchars["sup2"] =   178 
htmlchars["sup3"] =   179 
htmlchars["acute"] =  180 
htmlchars["micro"] =  181 
htmlchars["para"] =   182 
htmlchars["middot"] = 183 
htmlchars["cedil"] =  184 
htmlchars["sup1"] =   185 
htmlchars["ordm"] =   186 
htmlchars["raquo"] =  187 
htmlchars["frac14"] = 188 
htmlchars["frac12"] = 189 
htmlchars["frac34"] = 190 
htmlchars["iquest"] = 191 
htmlchars["Agrave"] = 192 
htmlchars["Aacute"] = 193 
htmlchars["Acirc"] =  194 
htmlchars["Atilde"] = 195 
htmlchars["Auml"] =   196 
htmlchars["Aring"] =  197 
htmlchars["AElig"] =  198 
htmlchars["Ccedil"] = 199 
htmlchars["Egrave"] = 200 
htmlchars["Eacute"] = 201 
htmlchars["Ecirc"] =  202 
htmlchars["Euml"] =   203 
htmlchars["Igrave"] = 204 
htmlchars["Iacute"] = 205 
htmlchars["Icirc"] =  206 
htmlchars["Iuml"] =   207 
htmlchars["ETH"] =    208 
htmlchars["Ntilde"] = 209 
htmlchars["Ograve"] = 210 
htmlchars["Oacute"] = 211 
htmlchars["Ocirc"] =  212 
htmlchars["Otilde"] = 213 
htmlchars["Ouml"] =   214 
htmlchars["times"] =  215 
htmlchars["Oslash"] = 216 
htmlchars["Ugrave"] = 217 
htmlchars["Uacute"] = 218 
htmlchars["Ucirc"] =  219 
htmlchars["Uuml"] =   220 
htmlchars["Yacute"] = 221 
htmlchars["THORN"] =  222 
htmlchars["szlig"] =  223 
htmlchars["agrave"] = 224 
htmlchars["aacute"] = 225 
htmlchars["acirc"] =  226 
htmlchars["atilde"] = 227 
htmlchars["auml"] =   228 
htmlchars["aring"] =  229 
htmlchars["aelig"] =  230 
htmlchars["ccedil"] = 231 
htmlchars["egrave"] = 232 
htmlchars["eacute"] = 233 
htmlchars["ecirc"] =  234 
htmlchars["euml"] =   235 
htmlchars["igrave"] = 236 
htmlchars["iacute"] = 237 
htmlchars["icirc"] =  238 
htmlchars["iuml"] =   239 
htmlchars["eth"] =    240 
htmlchars["ntilde"] = 241 
htmlchars["ograve"] = 242 
htmlchars["oacute"] = 243 
htmlchars["ocirc"] =  244 
htmlchars["otilde"] = 245 
htmlchars["ouml"] =   246 
htmlchars["divide"] = 247 
htmlchars["oslash"] = 248 
htmlchars["ugrave"] = 249 
htmlchars["uacute"] = 250 
htmlchars["ucirc"] =  251 
htmlchars["uuml"] =   252 
htmlchars["yacute"] = 253 
htmlchars["thorn"] =  254 
htmlchars["yuml"] =   255 
htmlchars["fnof"] =     402 
htmlchars["Alpha"] =    913 
htmlchars["Beta"] =     914 
htmlchars["Gamma"] =    915 
htmlchars["Delta"] =    916 
htmlchars["Epsilon"] =  917 
htmlchars["Zeta"] =     918 
htmlchars["Eta"] =      919 
htmlchars["Theta"] =    920 
htmlchars["Iota"] =     921 
htmlchars["Kappa"] =    922 
htmlchars["Lambda"] =   923 
htmlchars["Mu"] =       924 
htmlchars["Nu"] =       925 
htmlchars["Xi"] =       926 
htmlchars["Omicron"] =  927 
htmlchars["Pi"] =       928 
htmlchars["Rho"] =      929 
htmlchars["Sigma"] =    931 
htmlchars["Tau"] =      932 
htmlchars["Upsilon"] =  933 
htmlchars["Phi"] =      934 
htmlchars["Chi"] =      935 
htmlchars["Psi"] =      936 
htmlchars["Omega"] =    937 
htmlchars["alpha"] =    945 
htmlchars["beta"] =     946 
htmlchars["gamma"] =    947 
htmlchars["delta"] =    948 
htmlchars["epsilon"] =  949 
htmlchars["zeta"] =     950 
htmlchars["eta"] =      951 
htmlchars["theta"] =    952 
htmlchars["iota"] =     953 
htmlchars["kappa"] =    954 
htmlchars["lambda"] =   955 
htmlchars["mu"] =       956 
htmlchars["nu"] =       957 
htmlchars["xi"] =       958 
htmlchars["omicron"] =  959 
htmlchars["pi"] =       960 
htmlchars["rho"] =      961 
htmlchars["sigmaf"] =   962 
htmlchars["sigma"] =    963 
htmlchars["tau"] =      964 
htmlchars["upsilon"] =  965 
htmlchars["phi"] =      966 
htmlchars["chi"] =      967 
htmlchars["psi"] =      968 
htmlchars["omega"] =    969 
htmlchars["thetasym"] = 977 
htmlchars["upsih"] =    978 
htmlchars["piv"] =      982 
htmlchars["bull"] =     8226 
htmlchars["hellip"] =   8230 
htmlchars["prime"] =    8242 
htmlchars["Prime"] =    8243 
htmlchars["oline"] =    8254 
htmlchars["frasl"] =    8260 
htmlchars["weierp"] =   8472 
htmlchars["image"] =    8465 
htmlchars["real"] =     8476 
htmlchars["trade"] =    8482 
htmlchars["alefsym"] =  8501 
htmlchars["larr"] =     8592 
htmlchars["uarr"] =     8593 
htmlchars["rarr"] =     8594 
htmlchars["darr"] =     8595 
htmlchars["harr"] =     8596 
htmlchars["crarr"] =    8629 
htmlchars["lArr"] =     8656 
htmlchars["uArr"] =     8657 
htmlchars["rArr"] =     8658 
htmlchars["dArr"] =     8659 
htmlchars["hArr"] =     8660 
htmlchars["forall"] =   8704 
htmlchars["part"] =     8706 
htmlchars["exist"] =    8707 
htmlchars["empty"] =    8709 
htmlchars["nabla"] =    8711 
htmlchars["isin"] =     8712 
htmlchars["notin"] =    8713 
htmlchars["ni"] =       8715 
htmlchars["prod"] =     8719 
htmlchars["sum"] =      8721 
htmlchars["minus"] =    8722 
htmlchars["lowast"] =   8727 
htmlchars["radic"] =    8730 
htmlchars["prop"] =     8733 
htmlchars["infin"] =    8734 
htmlchars["ang"] =      8736 
htmlchars["and"] =      8743 
htmlchars["or"] =       8744 
htmlchars["cap"] =      8745 
htmlchars["cup"] =      8746 
htmlchars["int"] =      8747 
htmlchars["there4"] =   8756 
htmlchars["sim"] =      8764 
htmlchars["cong"] =     8773 
htmlchars["asymp"] =    8776 
htmlchars["ne"] =       8800 
htmlchars["equiv"] =    8801 
htmlchars["le"] =       8804 
htmlchars["ge"] =       8805 
htmlchars["sub"] =      8834 
htmlchars["sup"] =      8835 
htmlchars["nsub"] =     8836 
htmlchars["sube"] =     8838 
htmlchars["supe"] =     8839 
htmlchars["oplus"] =    8853 
htmlchars["otimes"] =   8855 
htmlchars["perp"] =     8869 
htmlchars["sdot"] =     8901 
htmlchars["lceil"] =    8968 
htmlchars["rceil"] =    8969 
htmlchars["lfloor"] =   8970 
htmlchars["rfloor"] =   8971 
htmlchars["lang"] =     9001 
htmlchars["rang"] =     9002 
htmlchars["loz"] =      9674 
htmlchars["spades"] =   9824 
htmlchars["clubs"] =    9827 
htmlchars["hearts"] =   9829 
htmlchars["diams"] =    9830 
htmlchars["quot"] =    34   
htmlchars["amp"] =     38   
htmlchars["lt"] =      60   
htmlchars["gt"] =      62   
htmlchars["OElig"] =   338  
htmlchars["oelig"] =   339  
htmlchars["Scaron"] =  352  
htmlchars["scaron"] =  353  
htmlchars["Yuml"] =    376  
htmlchars["circ"] =    710  
htmlchars["tilde"] =   732  
htmlchars["ensp"] =    8194 
htmlchars["emsp"] =    8195 
htmlchars["thinsp"] =  8201 
htmlchars["zwnj"] =    8204 
htmlchars["zwj"] =     8205 
htmlchars["lrm"] =     8206 
htmlchars["rlm"] =     8207 
htmlchars["ndash"] =   8211 
htmlchars["mdash"] =   8212 
htmlchars["lsquo"] =   8216 
htmlchars["rsquo"] =   8217 
htmlchars["sbquo"] =   8218 
htmlchars["ldquo"] =   8220 
htmlchars["rdquo"] =   8221 
htmlchars["bdquo"] =   8222 
htmlchars["dagger"] =  8224 
htmlchars["Dagger"] =  8225 
htmlchars["permil"] =  8240 
htmlchars["lsaquo"] =  8249 
htmlchars["rsaquo"] =  8250 
htmlchars["euro"] =   8364  


# This just converts html character entity references to
# unicode characters. 
def decodehtmlchars(str, failchar = '?'):
    result = ""
    index = 0

    while True:
            entref = str.find("&", index)
            if entref == -1:
                break

            entrefend = str.find(";", index)

            if entrefend == -1:
                result = result + str[index:entref+1]
                index = entref + 1
                continue

            try:
                if str[entref + 1] == "#":
                    if str[entref + 2].lower() == "x":
                        chr = unichr(int(str[entref + 3 : entrefend], 16))
                    else:
                        chr = unichr(int(str[entref + 2 : entrefend]))
                else:
                    chr = unichr(htmlchars[str[entref + 1 : entrefend]])
            except:
                chr = failchar

            result = result + str[index:entref]  + chr

            index = entrefend + 1

    result = result + str[index:]
    return result


#-------------- COLLAPSING OF HTML WHITESPACE ------------------
# replaces whitespace with single inter-word character
# http://www.w3.org/TR/html4/struct/text.html#whitespace

htmlwhitespace = [ 0x20, 0x09, 0x0C, 0x200B, 0x0D, 0x0A ] 

def collapsehtmlwhitespace(str, space = ' '):
    result = ""
    first = True

    for c in str:
        if ord(c) in htmlwhitespace:
            if first == True:
                result += space
                first = False
            else:
                pass
        else:
            result += c
            first = True

    return result

def decodehtml(str, space = ' ', failchar = '?'):

    result = decodehtmlchars(str, failchar) 
    result = collapsehtmlwhitespace(result, space)
    return result

    
if __name__ == "__main__":
    import sys
    print decodehtmlstr(sys.argv[1])


#------------------------------------------------------

def escapeamp(str):
    result = ""
    for i in range(len(str)):
        if str[i] != '&':
            result += str[i]
        else:
            result += '&&'

    return result

    
    
