import urllib
import cgi
import json
import base64
from functools import partial

import pytest
import requests

TEST_SERVER_HOST = 'http://localhost:8888'

# custom asserts

def assert_required_argument(url, argument, method='GET',
                             error_code=None,
                             error_description=None,
                             headers=None):
    resp = requests.request(method, url, headers=headers)
    assert 400 == resp.status_code
    assert 'application/json; charset=UTF-8' == resp.headers['content-type']
    
    body = json.loads(resp.content)    
    assert error_code == body['error']
    assert error_description == body['error_description']

def assert_error_response(response, error_code, status_code=400):
    assert status_code == response.status_code
    assert 'application/json; charset=UTF-8' == response.headers['content-type']
    assert {'error': error_code} == json.loads(response.content)


# helpers

def build_url(host, path, query=None):
    query = query or {}
    return u'{0}/{1}?{2}'.format(host.rstrip('/'),
                                 path.lstrip('/'),
                                 urllib.urlencode(query))

# urls used on tests

build_authorize_url = partial(build_url, TEST_SERVER_HOST, '/authorize')
build_access_token_url = partial(build_url, TEST_SERVER_HOST, '/access-token')

#
# test authorization request
#

def test_should_require_response_type_argument():
    assert_required_argument(build_authorize_url(), 'response_type',
                             error_code='invalid_request',
                             error_description='Parameter response_type is required')


def test_should_require_response_type_argument_to_be_code():
    assert_required_argument(build_authorize_url({'response_type': 'invalid'}),
                             'response_type',
                             error_code='invalid_request',
                             error_description='Parameter response_type should be code')


def test_should_require_client_id_argument():
    url = build_authorize_url({'response_type': 'code'})
    assert_required_argument(url, 'client_id',
                             error_code='invalid_request',
                             error_description='Parameter client_id is required')


def test_should_require_redirect_uri_argument():
    # XXX: it should be optional
    resp = requests.get(build_authorize_url({'client_id': '123',
                                       'response_type': 'code'}))
    assert 400 == resp.status_code
    assert 'Missing argument redirect_uri' in resp.content


def test_should_redirect_to_redirect_uri_argument_passing_auth_token():
    url = build_authorize_url({'client_id': '123',
                               'response_type': 'code',
                               'redirect_uri': 'http://callback'})
    resp = requests.get(url, allow_redirects=False)
    assert 302 == resp.status_code
    assert resp.headers['Location'].startswith('http://callback?code=')


def test_should_keep_get_query_string_from_redirect_uri_when_adding_code_parameter():
    url = build_authorize_url({'client_id': '123',
                         'response_type': 'code',
                         'redirect_uri': 'http://callback?param1=value1'})
    resp = requests.get(url, allow_redirects=False)
    assert 302 == resp.status_code
    assert resp.headers['Location'].startswith('http://callback?param1=value1&code=')


def test_should_generate_tokens_using_generate_authorization_token_function():
    # tokens generation is stubbed in tests/helpers.py
    url = build_authorize_url({'client_id': '123',
                               'response_type': 'code',
                               'redirect_uri': 'http://callback'})
    resp = requests.get(url, allow_redirects=False)
    assert 'http://callback?code=123-abc' == resp.headers['Location']


#
# test access token request
#

headers = {
    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
    'Authorization': 'Basic MTIzOmZvbw==',
    }

def test_should_require_content_type_header():
    resp = requests.post(build_access_token_url())
    assert 400 == resp.status_code
    assert_error_response(resp, 'invalid_request')


def test_should_require_authorization_header():
    invalid_headers = headers.copy()
    invalid_headers.pop('Authorization')
    resp = requests.post(build_access_token_url(), headers=invalid_headers)
    assert 400 == resp.status_code
    assert "Basic Authorization header is required" in resp.content


def test_authorization_header_should_be_basic():
    invalid_headers = headers.copy()
    invalid_headers['Authorization'] = 'Invalid andlksndklnd'
    resp = requests.post(build_access_token_url(), headers=invalid_headers)
    assert 400 == resp.status_code
    assert "Basic Authorization header is required" in resp.content


def test_should_require_grant_type_argument():
    assert_required_argument(build_access_token_url(), 'grant_type', 'POST',
                             error_code='invalid_request',
                             error_description='Parameter grant_type is required',
                             headers=headers)


def test_should_require_grant_type_argument_to_be_authorization_code():
    url = build_access_token_url({'grant_type': 'something-else'})
    assert_required_argument(url, 'grant_type', 'POST',
                             error_code='invalid_request',
                             error_description='Parameter grant_type should be authorization_code',
                             headers=headers)


def test_should_require_code_argument():
    url = build_access_token_url({'grant_type': 'authorization_code'})
    assert_required_argument(url, 'code', 'POST',
                             error_code='invalid_request',
                             error_description='Parameter code is required',
                             headers=headers)


def test_should_require_redirect_uri_argument():
    url = build_access_token_url({'grant_type': 'authorization_code',
                                  'code': 'foo'})
    assert_required_argument(url, 'redirect_uri', 'POST',
                             error_code='invalid_request',
                             error_description='Parameter redirect_uri is required',
                             headers=headers)

def test_should_return_access_token_if_valid_authorization_code():
    # tokens generation is stubbed in tests/helpers.py
    client_id = 'client1'
    code = request_authorization_code(client_id)

    url = build_access_token_url({'grant_type': 'authorization_code',
                                  'code': code,
                                  'redirect_uri': 'http://callback'})

    valid_headers = headers.copy()
    valid_headers['Authorization'] = build_basic_authorization_header(client_id, code)

    resp = requests.post(url, headers=valid_headers)

    assert 200 == resp.status_code
    assert 'application/json; charset=UTF-8' == resp.headers['content-type']

    body = json.loads(resp.content)
    assert ['access_token', 'expires_in'] == body.keys()
    assert '321-access-token' == body['access_token']


@pytest.mark.xfail
def test_should_validate_authorization_header_base64_format():
    assert 0


def test_should_return_invalid_grant_error_if_code_is_invalid():
    client_id = 'client1'
    code = request_authorization_code(client_id)

    url = build_access_token_url({'grant_type': 'authorization_code',
                                  'code': 'INVALID-CODE',
                                  'redirect_uri': 'http://callback'})

    valid_headers = headers.copy()
    valid_headers['Authorization'] = build_basic_authorization_header(client_id, code)

    resp = requests.post(url, headers=valid_headers)

    assert 400 == resp.status_code
    assert 'application/json; charset=UTF-8' == resp.headers['content-type']
    assert {'error': 'invalid_grant'} == json.loads(resp.content)


# def test_should_return_invalid_grant_error_if_code_is_invalid():
#     client_id = 'client1'
#     code = request_authorization_code(client_id)

#     url = build_access_token_url({'grant_type': 'authorization_code',
#                                   'code': 'INVALID-CODE',
#                                   'redirect_uri': 'http://callback'})

#     valid_headers = headers.copy()
#     valid_headers['Authorization'] = build_basic_authorization_header(client_id, code)

#     resp = requests.post(url, headers=valid_headers)

#     assert 400 == resp.status_code
#     assert 'application/json; charset=UTF-8' == resp.headers['content-type']
#     assert {'error': 'invalid_grant'} == json.loads(resp.content)



def request_authorization_code(client_id='123'):
    url = build_authorize_url({'client_id': client_id,
                               'response_type': 'code',
                               'redirect_uri': 'http://callback'})
    resp = requests.get(url, allow_redirects=False)
    code = get_code_from_url(resp.headers['Location'])
    return code

def get_code_from_url(url):
    query = dict(cgi.parse_qsl(url.split('?')[1]))
    return query['code']


def build_basic_authorization_header(client_id, code):
    digest = base64.b64encode('{0}:{1}'.format(client_id, code))
    return 'Basic {0}'.format(digest)
