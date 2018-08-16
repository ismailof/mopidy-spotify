from __future__ import unicode_literals

import itertools
import logging
import operator
import urlparse

from mopidy import models
from mopidy_spotify.web import parse_uri


# NOTE: This module is independent of libspotify and built using the Spotify
# Web APIs. As such it does not tie in with any of the regular code used
# elsewhere in the mopidy-spotify extensions. It is also intended to be used
# across both the 1.x and 2.x versions.

_API_MAX_IDS_PER_REQUEST = 50

_cache = {}  # (type, id) -> [Image(), ...]

logger = logging.getLogger(__name__)


# TODO: Merge some/all of this into WebSession
def get_images(web_session, uris):
    result = {}
    wl_type_getter = operator.attrgetter('type')
    weblinks = sorted((parse_uri(u) for u in uris), key=wl_type_getter)
    for uri_type, group in itertools.groupby(weblinks, wl_type_getter):
        batch = []
        for weblink in group:
            if weblink.id in _cache:
                result[weblink.uri] = _cache[weblink.id]
            elif weblink.type == 'playlist':
                result[weblink.uri] = _get_playlist_images(web_session, weblink.uri)
            else:
                batch.append(weblink)
                if len(batch) >= _API_MAX_IDS_PER_REQUEST:
                    result.update(
                        _process_uris(web_session._client, uri_type, batch))
                    batch = []
        result.update(_process_uris(web_session._client, uri_type, batch))
    return result

def _get_playlist_images(web_session, uri):
    web_playlist = web_session.get_playlist(uri)
    logger.info(web_playlist)
    if not web_playlist or 'images' not in web_playlist:
        return []
    return [_translate_image(image) for image in web_playlist['images']]

def _process_uris(web_client, uri_type, uris):
    result = {}
    ids = [u.id for u in uris]
    ids_to_uris = {u.id: u for u in uris}

    if not uris:
        return result

    data = web_client.get(uri_type + 's', params={'ids': ','.join(ids)})
    for item in data.get(uri_type + 's', []):
        if not item:
            continue
        uri = ids_to_uris[item['id']]
        if uri.id not in _cache:
            if uri_type == 'track':
                album_key = parse_uri(item['album']['uri']).id
                if album_key not in _cache:
                    _cache[album_key] = tuple(
                        _translate_image(i) for i in item['album']['images'])
                _cache[uri.id] = _cache[album_key]
            else:
                _cache[uri.id] = tuple(
                    _translate_image(i) for i in item['images'])
        result[uri.uri] = _cache[uri.id]

    return result


def _translate_image(i):
    return models.Image(uri=i['url'], height=i['height'], width=i['width'])
