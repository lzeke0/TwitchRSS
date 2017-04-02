# Feedformatter
# Copyright (c) 2008, Luke Maurits <luke@maurits.id.au>
# Copyright (c) 2015, Laszlo Zeke
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * The name of the author may not be used to endorse or promote products
#   derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

__version__ = "0.4"

from cStringIO import StringIO

# This "staircase" of import attempts is ugly.  If there's a nicer way to do
# this, please let me know!
try:
    import xml.etree.cElementTree as ET
except ImportError:
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        try:
            import cElementTree as ET
        except ImportError:
            try:
                from elementtree import ElementTree as ET
            except ImportError:
                raise ImportError("Could not import any form of element tree!")

try:
    from xml.dom.ext import PrettyPrint
    from xml.dom.ext.reader.Sax import FromXml
    feedformatterCanPrettyPrint = True
except ImportError:
    feedformatterCanPrettyPrint = False

from time import time, strftime, localtime, mktime, struct_time, timezone

# RSS 1.0 Functions ----------

_rss1_channel_mappings = (
    (("title",), "title"),
    (("link", "url"), "link"),
    (("description", "desc", "summary"), "description")
)

_rss1_item_mappings = (
    (("title",), "title"),
    (("link", "url"), "link"),
    (("description", "desc", "summary"), "description")
)

# RSS 2.0 Functions ----------

_rss2_channel_mappings = (
    (("title",), "title"),
    (("link", "url"), "link"),
    (("description", "desc", "summary"), "description"),
    (("pubDate", "pubdate", "date", "published", "updated"), "pubDate", lambda(x): _format_datetime("rss2",x)),
    (("category",), "category"),
    (("language",), "language"),
    (("copyright",), "copyright"),
    (("webMaster",), "webmaster"),
    (("image",), "image"),
    (("skipHours",), "skipHours"),
    (("skipDays",), "skipDays"),
    (("ttl",), "ttl")
)

_rss2_item_mappings = (
    (("title",), "title"),
    (("link", "url"), "link"),
    (("description", "desc", "summary"), "description"),
    (("guid", "id"), "guid"),
    (("pubDate", "pubdate", "date", "published", "updated"), "pubDate", lambda(x): _format_datetime("rss2",x)),
    (("category",), "category"),
    (("author",), "author", lambda(x): _rssify_author(x))
)

# Atom 1.0 ----------

_atom_feed_mappings = (
    (("title",), "title"),
    (("link", "url"), "id"),
    (("description", "desc", "summary"), "subtitle"),
    (("pubDate", "pubdate", "date", "published", "updated"), "pubDate", lambda(x): _format_datetime("atom",x)),
    (("category",), "category"),
    (("author",), "author", lambda(x): _atomise_author(x))
)

_atom_item_mappings = (
    (("title",), "title"),
    (("link", "url"), "id"),
    (("link", "url"), "link", lambda(x): _atomise_link(x)),
    (("description", "desc", "summary"), "summary"),
    (("pubDate", "pubdate", "date", "published", "updated"), "pubDate", lambda(x): _format_datetime("atom",x)),
    (("category",), "category"),
    (("author",), "author", lambda(x): _atomise_author(x))
)

def _get_tz_offset():

    """
    Return the current timezone's offset from GMT as a string
    in the format +/-HH:MM, as required by RFC3339.
    """

    seconds = -1*timezone    # Python gets the offset backward! >:(
    minutes = seconds/60
    hours = minutes/60
    minutes = minutes - hours*60
    if seconds < 0:
        return "-%02d:%d" % (hours, minutes)
    else:
        return "+%02d:%d" % (hours, minutes)

def _convert_datetime(time):

    """
    Convert time, which may be one of a whole lot of things, into a
    standard 9 part time tuple.
    """

    if (type(time) is tuple and len(time) ==9) or type(time) is struct_time:
        # Already done!
        return time
    elif type(time) is int or type(time) is float:
        # Assume this is a seconds-since-epoch time
        return localtime(time)
    elif type(time) is str:    
        if time.isalnum():
            # String is alphanumeric - a time stamp?
            try:
                return strptime(time, "%a, %d %b %Y %H:%M:%S %Z")
            except ValueError:
                raise Exception("Unrecongised time format!")        
        else:
            # Maybe this is a string of an epoch time?
            try:
                return localtime(float(time))
            except ValueError:
                # Guess not.
                raise Exception("Unrecongised time format!")                 
    else:
        # No idea what this is.  Give up!
        raise Exception("Unrecongised time format!")

def _format_datetime(feed_type, time):

    """
    Convert some representation of a date and time into a string which can be
    used in a validly formatted feed of type feed_type.  Raise an
    Exception if this cannot be done.
    """
    
    # First, convert time into a time structure
    time = _convert_datetime(time)

    # Then, convert that to the appropriate string
    if feed_type is "rss2":
        return strftime("%a, %d %b %Y %H:%M:%S UT", time)
    elif feed_type is "atom":
        return strftime("%Y-%m-%dT%H:%M:%S", time) + _get_tz_offset();

def _atomise_link(link):

    if type(link) is dict:
        return dict
    else:
        return {"href" : link}
        
def _atomise_author(author):

    """
    Convert author from whatever it is to a dictionary representing an
    atom:Person construct.
    """

    if type(author) is dict:
        return author
    else:
        if author.startswith("http://") or author.startswith("www"):
            # This is clearly a URI
            return {"uri" : author}
        elif "@" in author and "." in author:
            # This is most probably an email address
            return {"email" : author}
        else:
            # Must be a name
            return {"name" : author}

def _rssify_author(author):

    """
    Convert author from whatever it is to a plain old email string for
    use in an RSS 2.0 feed.
    """
    
    if type(author) is dict:
        try:
            return author["email"]
        except KeyError:
            return None
    else:
        if "@" in author and "." in author:
            # Probably an email address
            return author
        else:
            return None

def _add_subelems(root_element, mappings, dictionary):

    """
    Add one subelement to root_element for each key in dictionary
    which is supported by a mapping in mappings
    """
    for mapping in mappings:
        for key in mapping[0]:
            if key in dictionary:
                if len(mapping) == 2:
                    value = dictionary[key]
                elif len(mapping) == 3:
                    value = mapping[2](dictionary[key])
                _add_subelem(root_element, mapping[1], value)
                break                
    
def _add_subelem(root_element, name, value):

    if value is None:
        return

    if type(value) is dict:
        ### HORRIBLE HACK!
        if name=="link":
            ET.SubElement(root_element, name, href=value["href"])
        else:
            subElem = ET.SubElement(root_element, name)
            for key in value:
                _add_subelem(subElem, key, value[key])
    else:
        if name == "guid" and not value.startswith("http"):
            el = ET.SubElement(root_element, name)
            el.text = value
            el.attrib["isPermaLink"] = "false"
        else:
            ET.SubElement(root_element, name).text = value


def _stringify(tree, pretty):

    """
    Turn an ElementTree into a string, optionally with line breaks and indentation.
    """

    if pretty and feedformatterCanPrettyPrint:
        string = StringIO()
        doc = FromXml(ET.tostring(tree))
        PrettyPrint(doc,string,indent="    ")
        return string.getvalue()
    else:
        return ET.tostring(tree)

class Feed:

    ### INTERNAL METHODS ------------------------------
    
    def __init__(self, feed=None, items=None):

        if feed:
            self.feed = feed
        else:
            self.feed = {}
        if items:
            self.items = items
        else:
            self.items = []
        self.entries = self.items

    ### RSS 1.0 STUFF ------------------------------
        
    def validate_rss1(self):

        """Raise an InvalidFeedException if the feed cannot be validly
        formatted as RSS 1.0."""

        # <channel> must contain "title"
        if "title" not in self.feed:
            raise InvalidFeedException("The channel element of an "
            "RSS 1.0 feed must contain a title subelement")

        # <channel> must contain "link"
        if "link" not in self.feed:
            raise InvalidFeedException("The channel element of an "
            " RSS 1.0 feeds must contain a link subelement")

        # <channel> must contain "description"
        if "description" not in self.feed:
            raise InvalidFeedException("The channel element of an "
            "RSS 1.0 feeds must contain a description subelement")

        # Each <item> must contain "title" and "link"
        for item in self.items:
            if "title" not in item:
                raise InvalidFeedException("Each item element in an RSS 1.0 "
                "feed must contain a title subelement")
            if "link" not in item:
                raise InvalidFeedException("Each item element in an RSS 1.0 "
                "feed must contain a link subelement")
        
    def format_rss1_string(self, validate=True, pretty=False):

        """Format the feed as RSS 1.0 and return the result as a string."""

        if validate:
            self.validate_rss1()
        RSS1root = ET.Element( 'rdf:RDF', 
            {"xmlns:rdf" : "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
             "xmlns" : "http://purl.org/rss/1.0/"} )
        RSS1channel = ET.SubElement(RSS1root, 'channel',
            {"rdf:about" : self.feed["link"]})
        _add_subelems(RSS1channel, _rss1_channel_mappings, self.feed)
        RSS1contents = ET.SubElement(RSS1channel, 'items')
        RSS1contents_seq = ET.SubElement (RSS1contents, 'rdf:Seq')
        for item in self.items:
            ET.SubElement(RSS1contents_seq, 'rdf:li', resource=item["link"])
        for item in self.items:
            RSS1item = ET.SubElement (RSS1root, 'item',
                {"rdf:about" : item["link"]})
            _add_subelems(RSS1item, _rss1_item_mappings, item)
        return _stringify(RSS1root, pretty=pretty)

    def format_rss1_file(self, filename, validate=True, pretty=False):

        """Format the feed as RSS 1.0 and save the result to a file."""

        string = self.format_rss1_string(validate, pretty)
        fp = open(filename, "w")
        fp.write(string)
        fp.close()

    ### RSS 2.0 STUFF ------------------------------

    def validate_rss2(self):

        """Raise an InvalidFeedException if the feed cannot be validly
        formatted as RSS 2.0."""

        # <channel> must contain "title"
        if "title" not in self.feed:
            raise InvalidFeedException("The channel element of an "
            "RSS 2.0 feed must contain a title subelement")

        # <channel> must contain "link"
        if "link" not in self.feed:
            raise InvalidFeedException("The channel element of an "
            " RSS 2.0 feeds must contain a link subelement")

        # <channel> must contain "description"
        if "description" not in self.feed:
            raise InvalidFeedException("The channel element of an "
            "RSS 2.0 feeds must contain a description subelement")

        # Each <item> must contain at least "title" OR "description"
        for item in self.items:
            if not ("title" in item or "description" in item):
                raise InvalidFeedException("Each item element in an RSS 2.0 "
                "feed must contain at least a title or description subelement")

    def format_rss2_string(self, validate=True, pretty=False):

        """Format the feed as RSS 2.0 and return the result as a string."""

        if validate:
            self.validate_rss2()
        RSS2root = ET.Element( 'rss', {'version':'2.0'} )
        RSS2channel = ET.SubElement( RSS2root, 'channel' )
        _add_subelems(RSS2channel, _rss2_channel_mappings, self.feed)
        for item in self.items:            
            RSS2item = ET.SubElement ( RSS2channel, 'item' )
            _add_subelems(RSS2item, _rss2_item_mappings, item)
        return _stringify(RSS2root, pretty=pretty)

    def format_rss2_file(self, filename, validate=True, pretty=False):

        """Format the feed as RSS 2.0 and save the result to a file."""

        string = self.format_rss2_string(validate, pretty)
        fp = open(filename, "w")
        fp.write(string)
        fp.close()

    ### ATOM STUFF ------------------------------

    def validate_atom(self):

        """Raise an InvalidFeedException if the feed cannot be validly
        formatted as Atom 1.0."""

        # Must have at least one "author" element in "feed" OR at least
        # "author" element in each "entry".
        if "author" not in self.feed:
            for entry in self.entries:
                if "author" not in entry:
                    raise InvalidFeedException("Atom feeds must have either at "
                    "least one author element in the feed element or at least "
                    " one author element in each entry element")

    def format_atom_string(self, validate=True, pretty=False):

        """Format the feed as Atom 1.0 and return the result as a string."""

        if validate:
            self.validate_atom()
        AtomRoot = ET.Element( 'feed', {"xmlns":"http://www.w3.org/2005/Atom"} )
        _add_subelems(AtomRoot, _atom_feed_mappings, self.feed)
        for entry in self.entries:
            AtomItem = ET.SubElement ( AtomRoot, 'entry' )
            _add_subelems(AtomItem, _atom_item_mappings, entry)
        return _stringify(AtomRoot, pretty=pretty)

    def format_atom_file(self, filename, validate=True, pretty=False):

        """Format the feed as Atom 1.0 and save the result to a file."""

        string = self.format_atom_string(validate, pretty)
        fp = open(filename, "w")
        fp.write(string)
        fp.close()

class InvalidFeedException(Exception):

    pass

### FACTORY FUNCTIONS ------------------------------

def fromUFP(ufp):

    return Feed(ufp["feed"], ufp["items"])

### MAIN ------------------------------

def main():

    feed = Feed()
    feed.feed["title"] = "Test Feed"
    feed.feed["link"] = "http://code.google.com/p/feedformatter/"
    feed.feed["author"] = "Luke Maurits"
    feed.feed["description"] = "A simple test feed for the feedformatter project"
    item = {}
    item["title"] = "Test item"
    item["link"] = "http://www.python.org"
    item["description"] = "Python programming language"
    item["guid"] = "1234567890"
    feed.items.append(item)
    print("---- RSS 1.0 ----")
    print feed.format_rss1_string(pretty=True)
    print("---- RSS 2.0 ----")
    print feed.format_rss2_string(pretty=True)
    print("---- Atom 1.0 ----")
    print feed.format_atom_string(pretty=True)

if __name__ == "__main__":
    main()
