"""
Created on Mar 13, 2013

@author: dmitchell
"""
from __future__ import absolute_import
import re
import logging
import inspect
from abc import ABCMeta, abstractmethod
from urllib import quote

from bson.objectid import ObjectId
from bson.errors import InvalidId

from xmodule.modulestore.exceptions import InvalidLocationError, \
    InsufficientSpecificationError, OverSpecificationError

from .parsers import parse_url, parse_guid, parse_course_id, parse_block_ref

log = logging.getLogger(__name__)


class Locator(object):
    """
    A locator is like a URL, it refers to a course resource.

    Locator is an abstract base class: do not instantiate
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def url(self):
        """
        Return a string containing the URL for this location. Raises
        InsufficientSpecificationError if the instance doesn't have a
        complete enough specification to generate a url
        """
        raise InsufficientSpecificationError()

    def quoted_url(self):
        return quote(self.url(), '@;#')

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        '''
        repr(self) returns something like this: CourseLocator("edu.mit.eecs.6002x")
        '''
        classname = self.__class__.__name__
        if classname.find('.') != -1:
            classname = classname.split['.'][-1]
        return '%s("%s")' % (classname, unicode(self))

    def __str__(self):
        '''
        str(self) returns something like this: "edu.mit.eecs.6002x"
        '''
        return unicode(self).encode('utf8')

    def __unicode__(self):
        '''
        unicode(self) returns something like this: "edu.mit.eecs.6002x"
        '''
        return self.url()

    @abstractmethod
    def version(self):
        """
        Returns the ObjectId referencing this specific location.
        Raises InsufficientSpecificationError if the instance
        doesn't have a complete enough specification.
        """
        raise InsufficientSpecificationError()

    def set_property(self, property_name, new):
        """
        Initialize property to new value.
        If property has already been initialized to a different value, raise an exception.
        """
        current = getattr(self, property_name)
        if current and current != new:
            raise OverSpecificationError('%s cannot be both %s and %s' %
                                         (property_name, current, new))
        setattr(self, property_name, new)


class CourseLocator(Locator):
    """
    Examples of valid CourseLocator specifications:
     CourseLocator(version_guid=ObjectId('519665f6223ebd6980884f2b'))
     CourseLocator(course_id='edu.mit.eecs.6002x')
     CourseLocator(course_id='edu.mit.eecs.6002x;published')
     CourseLocator(course_id='edu.mit.eecs.6002x', revision='published')
     CourseLocator(url='edx://@519665f6223ebd6980884f2b')
     CourseLocator(url='edx://edu.mit.eecs.6002x')
     CourseLocator(url='edx://edu.mit.eecs.6002x;published')

    Should have at lease a specific course_id (id for the course as if it were a project w/
    versions) with optional 'revision' (must be 'draft', 'published', or None),
    or version_guid (which points to a specific version). Can contain both in which case
    the persistence layer may raise exceptions if the given version != the current such version
    of the course.
    """

    # Default values
    version_guid = None
    course_id = None
    revision = None

    def __unicode__(self):
        """
        Return a string representing this location.
        """
        if self.course_id:
            result = self.course_id
            if self.revision:
                result += ';' + self.revision
            return result
        elif self.version_guid:
            return '@' + str(self.version_guid)
        else:
            #raise InsufficientSpecificationError("missing course_id or version_guid")
            return '<InsufficientSpecificationError: missing course_id or version_guid>'

    def url(self):
        """
        Return a string containing the URL for this location.
        """
        return 'edx://' + unicode(self)

    def validate_args(self, url, version_guid, course_id, revision):
        """
        Validate provided arguments.
        """
        need_oneof = set(('url', 'version_guid', 'course_id'))
        args, _, _, values = inspect.getargvalues(inspect.currentframe())
        provided_args = [a for a in args if a != 'self' and values[a] is not None]
        arg_dict = dict([(a, values[a]) for a in provided_args])
        if len(need_oneof.intersection(provided_args)) == 0:
            raise InsufficientSpecificationError("Must provide one of these args: %s " %
                                                 list(need_oneof))

    def set_course_id(self, new):
        """
        Initialize course_id to new value.
        If course_id has already been initialized to a different value, raise an exception.
        """
        self.set_property('course_id', new)

    def set_revision(self, new):
        """
        Initialize revision to new value.
        If revision has already been initialized to a different value, raise an exception.
        """
        self.set_property('revision', new)

    def set_version_guid(self, new):
        """
        Initialize version_guid to new value.
        If version_guid has already been initialized to a different value, raise an exception.
        """
        self.set_property('version_guid', new)

    def __init__(self, url=None, version_guid=None, course_id=None, revision=None):
        """
        Construct a CourseLocator
        Caller may provide url (but no other parameters).
        Caller may provide version_guid (but no other parameters).
        Caller may provide course_id (optionally provide revision).

        Resulting CourseLocator will have either a version_guid property
        or a course_id (with optional revision) property, or both.

        version_guid must be an instance of bson.objectid.ObjectId or None
        url, course_id, and revision must be strings or None

        """
        self.validate_args(url, version_guid, course_id, revision)
        if url:
            self.init_from_url(url)
        if version_guid:
            self.init_from_version_guid(version_guid)
        if course_id or revision:
            self.init_from_course_id(course_id, revision)
        assert self.version_guid or self.course_id, \
            "Either version_guid or course_id should be set."

    def init_from_url(self, url):
        """
        url must be a string beginning with 'edx://' and containing
        either a valid version_guid or course_id (with optional revision)
        If a block ('#HW3') is present, it is ignored.
        """
        if isinstance(url, Locator):
            url = url.url()
        assert isinstance(url, basestring), \
            '%s is not an instance of basestring' % url
        parse = parse_url(url)
        assert parse, 'Could not parse "%s" as a url' % url
        if 'version_guid' in parse:
            new_guid = parse['version_guid']
            try:
                self.set_version_guid(ObjectId(new_guid))
            except InvalidId:
                raise ValueError(
                    '"%s" is not a valid version_guid' % new_guid
                )

        else:
            self.set_course_id(parse['id'])
            self.set_revision(parse['revision'])

    def init_from_version_guid(self, version_guid):
        """
        version_guid must be an instance of bson.objectid.ObjectId
        """
        assert isinstance(version_guid, ObjectId), \
            '%s is not an instance of ObjectId' % version_guid
        self.set_version_guid(version_guid)

    def init_from_course_id(self, course_id, explicit_revision=None):
        """
        Course_id is a string like 'edu.mit.eecs.6002x' or 'edu.mit.eecs.6002x;published'.

        Revision (optional) is a string like 'published'.
        It may be provided explicitly (explicit_revision) or embedded into course_id.
        If revision is part of course_id ("...;published"), parse it out separately.
        If revision is provided both ways, that's ok as long as they are the same value.

        If a block ('#HW3') is a part of course_id, it is ignored.

        """

        if course_id:
            if isinstance(course_id, CourseLocator):
                course_id = course_id.course_id
                assert course_id, "%s does not have a valid course_id"

            parse = parse_course_id(course_id)
            assert parse, 'Could not parse "%s" as a course_id' % course_id
            self.set_course_id(parse['id'])
            rev = parse['revision']
            if rev:
                self.set_revision(rev)
        if explicit_revision:
            self.set_revision(explicit_revision)

    def version(self):
        """
        Returns the ObjectId referencing this specific location.
        """
        return self.version_guid


class BlockUsageLocator(CourseLocator):
    """
    Encodes a location.

    Locations address modules (aka blocks) which are definitions situated in a
    course instance. Thus, a Location must identify the course and the occurrence of
    the defined element in the course. Courses can be a version of an offering, the
    current draft head, or the current production version.

    Locators can contain both a version and a course_id w/ revision. The split mongo functions
    may raise errors if these conflict w/ the current db state (i.e., the course's revision !=
    the version_guid)

    Locations can express as urls as well as dictionaries. They consist of
        course_identifier: course_guid | version_guid
        block : guid
        revision : 'draft' | 'published' (optional)
    """

    # Default value
    usage_id = None

    def __init__(self, url=None, version_guid=None, course_id=None,
                 revision=None, usage_id=None):
        """
        Construct a BlockUsageLocator
        Caller may provide url, version_guid, or course_id, and optionally provide revision.

        The usage_id may be specified, either explictly or as part of
        the url or course_id. If omitted, the locator is created but it
        has not yet been initialized.

        Resulting BlockUsageLocator will have a usage_id property.
        It will have either a version_guid property or a course_id (with optional revision) property, or both.

        version_guid must be an instance of bson.objectid.ObjectId or None
        url, course_id, revision, and usage_id must be strings or None

        """
        self.validate_args(url, version_guid, course_id, revision)
        if url:
            self.init_block_ref_from_url(url)
        if course_id:
            self.init_block_ref_from_course_id(course_id)
        if usage_id:
            self.init_block_ref(usage_id)
        CourseLocator.__init__(self,
                               url=url,
                               version_guid=version_guid,
                               course_id=course_id,
                               revision=revision)

    def is_initialized(self):
        """
        Returns True if usage_id has been initialized, else returns False
        """
        return self.usage_id is not None

    def as_course_locator(self):
        """
        Returns a copy of itself as a CourseLocator.
        The copy has the same information as the original, but without a usage_id.
        """
        return CourseLocator(course_id=self.course_id,
                             version_guid=self.version_guid,
                             revision=self.revision)

    def version_agnostic(self):
        """
        Returns a copy of itself.
        If both version_guid and course_id are known, use a blank course_id in the copy.

        We don't care if the locator's version is not the current head; so, avoid version conflict
        by reducing info.

        :param block_locator:
        """
        if self.course_id and self.version_guid:
            return BlockUsageLocator(version_guid=self.version_guid,
                                     revision=self.revision,
                                     usage_id=self.usage_id)
        else:
            return BlockUsageLocator(course_id=self.course_id,
                                     revision=self.revision,
                                     usage_id=self.usage_id)

    def set_usage_id(self, new):
        """
        Initialize usage_id to new value.
        If usage_id has already been initialized to a different value, raise an exception.
        """
        self.set_property('usage_id', new)

    def init_block_ref(self, block_ref):
        parse = parse_block_ref(block_ref)
        assert parse, 'Could not parse "%s" as a block_ref' % block_ref
        self.set_usage_id(parse['block'])

    def init_block_ref_from_url(self, url):
        if isinstance(url, Locator):
            url = url.url()
        parse = parse_url(url)
        assert parse, 'Could not parse "%s" as a url' % url
        block = parse.get('block', None)
        if block:
            self.set_usage_id(block)

    def init_block_ref_from_course_id(self, course_id):
        if isinstance(course_id, CourseLocator):
            course_id = course_id.course_id
            assert course_id, "%s does not have a valid course_id"
        parse = parse_course_id(course_id)
        assert parse, 'Could not parse "%s" as a course_id' % course_id
        block = parse.get('block', None)
        if block:
            self.set_usage_id(block)

    def __unicode__(self):
        """
        Return a string representing this location.
        """
        rep = CourseLocator.__unicode__(self)
        if self.usage_id is None:
            # usage_id has not been initialized
            return rep + '#NONE'
        else:
            return rep + '#' + self.usage_id


class DescriptionLocator(Locator):
    """
    Container for how to locate a description
    """

    def __init__(self, definition_id):
        self.definition_id = definition_id

    def __unicode__(self):
        '''
        Return a string representing this location.
        unicode(self) returns something like this: "@519665f6223ebd6980884f2b"
        '''
        return '@' + str(self.definition_guid)

    def url(self):
        """
        Return a string containing the URL for this location.
        url(self) returns something like this: 'edx://@519665f6223ebd6980884f2b'
        """
        return 'edx://' + unicode(self)

    def version(self):
        """
        Returns the ObjectId referencing this specific location.
        """
        return self.definition_guid


class VersionTree(object):
    """
    Holds trees of Locators to represent version histories.
    """
    def __init__(self, locator, tree_dict=None):
        """
        :param locator: must be version specific (Course has version_guid or definition had id)
        """
        assert isinstance(locator, Locator) and not inspect.isabstract(locator), \
            "locator must be a concrete subclass of Locator"
        assert locator.version(), \
            "locator must be version specific (Course has version_guid or definition had id)"
        self.locator = locator
        if tree_dict is None:
            self.children = []
        else:
            self.children = [VersionTree(child, tree_dict)
                             for child in tree_dict.get(locator.version(), [])]