# coding: utf-8
import os
import sys

from beaker.cache import clsmap, Cache
from beaker.middleware import CacheMiddleware, SessionMiddleware
from beaker.exceptions import InvalidCacheBackendError
from nose import SkipTest
from webtest import TestApp
from pymongo.connection import Connection
import unittest
import time

try:
    clsmap['mongodb_gridfs']._init_dependencies()
except InvalidCacheBackendError:
    raise SkipTest("an appropriate mmongodb backend is not installed")

uri = 'mongodb://localhost/test.beaker'

_mongo = Connection('localhost').test

def setup():
    _mongo.beaker.chunks.drop()
    _mongo.beaker.files.drop()

def teardown():
    import shutil
    shutil.rmtree('./cache', True)
    _mongo.beaker.chunks.drop()
    _mongo.beaker.files.drop()

def simple_session_app(environ, start_response):
    session = environ['beaker.session']
    sess_id = environ.get('SESSION_ID')
    if environ['PATH_INFO'].startswith('/invalid'):
        # Attempt to access the session
        id = session.id
        session['value'] = 2
    else:
        if sess_id:
            session = session.get_by_id(sess_id)
        if not session:
            start_response('200 OK', [('Content-type', 'text/plain')])
            return ["No session id of %s found." % sess_id]
        if not session.has_key('value'):
            session['value'] = 0
        session['value'] += 1
        if not environ['PATH_INFO'].startswith('/nosave'):
            session.save()
    start_response('200 OK', [('Content-type', 'text/plain')])
    return ['The current value is: %d, session id is %s' % (session['value'],
                                                            session.id)]

def simple_app(environ, start_response):
    extra_args = {}
    clear = False
    if environ.get('beaker.clear'):
        clear = True
    extra_args['type'] = 'mongodb_gridfs'
    extra_args['url'] = uri
    extra_args['expire'] = 86400
    extra_args['data_dir'] = './cache'
    cache = environ['beaker.cache'].get_cache('testcache', **extra_args)
    if clear:
        cache.clear()
    try:
        value = cache.get_value('value')
    except:
        value = 0
    cache.set_value('value', value+1)
    start_response('200 OK', [('Content-type', 'text/plain')])
    return ['The current value is: %s' % cache.get_value('value')]


def using_none_app(environ, start_response):
    extra_args = {}
    clear = False
    if environ.get('beaker.clear'):
        clear = True
    extra_args['type'] = 'mongodb_gridfs'
    extra_args['url'] = uri
    extra_args['expire'] = 86400
    extra_args['data_dir'] = './cache'
    cache = environ['beaker.cache'].get_cache('testcache', **extra_args)
    if clear:
        cache.clear()
    try:
        value = cache.get_value('value')
    except:
        value = 10
    cache.set_value('value', None)
    start_response('200 OK', [('Content-type', 'text/plain')])
    return ['The current value is: %s' % value]


def cache_manager_app(environ, start_response):
    cm = environ['beaker.cache']
    cm.get_cache('test')['test_key'] = 'test value'

    start_response('200 OK', [('Content-type', 'text/plain')])
    yield "test_key is: %s\n" % cm.get_cache('test')['test_key']
    cm.get_cache('test').clear()

    try:
        test_value = cm.get_cache('test')['test_key']
    except KeyError:
        yield "test_key cleared"
    else:
        yield "test_key wasn't cleared, is: %s\n" % \
            cm.get_cache('test')['test_key']


def test_session():
    app = TestApp(SessionMiddleware(simple_session_app, data_dir='./cache', type='mongodb_gridfs', url=uri))
    res = app.get('/')
    assert 'current value is: 1' in res
    res = app.get('/')
    assert 'current value is: 2' in res
    res = app.get('/')
    assert 'current value is: 3' in res


def test_session_invalid():
    app = TestApp(SessionMiddleware(simple_session_app, data_dir='./cache', type='mongodb_gridfs', url=uri))
    res = app.get('/invalid', headers=dict(Cookie='beaker.session.id=df7324911e246b70b5781c3c58328442; Path=/'))
    assert 'current value is: 2' in res


def test_has_key():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    o = object()
    cache.set_value("test", o)
    assert cache.has_key("test")
    assert "test" in cache
    assert not cache.has_key("foo")
    assert "foo" not in cache
    cache.remove_value("test")
    assert not cache.has_key("test")

def test_clearing_cache():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    cache.set_value('test', 20)
    cache.set_value('fred', 10)
    assert cache.has_key('test')
    assert 'test' in cache
    assert cache.has_key('fred')

    cache.clear()
    assert not cache.has_key('test')

def test_expiretime():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    cache.set_value('test', 20, expiretime=-10)
    cache.set_value('foo', 20)
    assert not cache.has_key('test')
    assert 'test' not in cache
    assert cache.has_key('foo')
    assert 'foo' in cache

def test_has_key_multicache():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    o = object()
    cache.set_value("test", o)
    assert cache.has_key("test")
    assert "test" in cache
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    assert cache.has_key("test")

def test_unicode_keys():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    o = object()
    cache.set_value(u'hiŏ', o)
    assert u'hiŏ' in cache
    assert u'hŏa' not in cache
    cache.remove_value(u'hiŏ')
    assert u'hiŏ' not in cache

def test_unicode_values():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    cache.set_value('test', u'hiŏ')
    assert 'test' in cache

def test_spaces_in_unicode_keys():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    o = object()
    cache.set_value(u'hi ŏ', o)
    assert u'hi ŏ' in cache
    assert u'hŏa' not in cache
    cache.remove_value(u'hi ŏ')
    assert u'hi ŏ' not in cache

def test_spaces_in_keys():
    cache = Cache('test', data_dir='./cache', url=uri, type='mongodb_gridfs')
    cache.set_value("has space", 24)
    assert cache.has_key("has space")
    assert 24 == cache.get_value("has space")
    cache.set_value("hasspace", 42)
    assert cache.has_key("hasspace")
    assert 42 == cache.get_value("hasspace")

def test_increment():
    app = TestApp(CacheMiddleware(simple_app))
    res = app.get('/', extra_environ={'beaker.clear':True})
    assert 'current value is: 1' in res
    res = app.get('/')
    assert 'current value is: 2' in res
    res = app.get('/')
    assert 'current value is: 3' in res

    app = TestApp(CacheMiddleware(simple_app))
    res = app.get('/', extra_environ={'beaker.clear':True})
    assert 'current value is: 1' in res
    res = app.get('/')
    assert 'current value is: 2' in res
    res = app.get('/')
    assert 'current value is: 3' in res

def test_cache_manager():
    app = TestApp(CacheMiddleware(cache_manager_app))
    res = app.get('/')
    assert 'test_key is: test value' in res
    assert 'test_key cleared' in res

def test_store_none():
    app = TestApp(CacheMiddleware(using_none_app))
    res = app.get('/', extra_environ={'beaker.clear':True})
    assert 'current value is: 10' in res
    res = app.get('/')
    assert 'current value is: None' in res

class TestMongoInit(unittest.TestCase):
    def test_uses_mongo_client(self):
        from mongodb_gridfs_beaker import MongoDBGridFSNamespaceManager
        cache = Cache('test', data_dir='./cache', url=uri, type="mongodb_gridfs")
        assert isinstance(cache.namespace, MongoDBGridFSNamespaceManager)


    def test_client(self):
        cache = Cache('test', data_dir='./cache', url=uri, type="mongodb_gridfs")
        o = object()
        cache.set_value("test", o)
        assert cache.has_key("test")
        assert "test" in cache
        assert not cache.has_key("foo")
        assert "foo" not in cache
        cache.remove_value("test")
        assert not cache.has_key("test")
