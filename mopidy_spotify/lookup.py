from __future__ import unicode_literals

import logging

import spotify

from mopidy_spotify import translator, utils, web


logger = logging.getLogger(__name__)

_VARIOUS_ARTISTS_URIS = [
    'spotify:artist:0LyfQWJT6nXafLPZqxe9Of',
]


def lookup(config, session, web_session, uri):
    try:
        web_link = web.parse_uri(uri)
        sp_link = session.get_link(uri)
    except ValueError as exc:
        logger.info('Failed to lookup "%s": %s', uri, exc)
        return []

    try:
        if sp_link.type is spotify.LinkType.TRACK:
            return list(_lookup_track(config, sp_link))
        elif sp_link.type is spotify.LinkType.ALBUM:
            return list(_lookup_album(config, sp_link))
        elif sp_link.type is spotify.LinkType.ARTIST:
            with utils.time_logger('Artist lookup'):
                return list(_lookup_artist(config, sp_link))
        elif web_link.type == 'playlist':
            return list(_lookup_playlist(web_session, config, uri))
        elif web_link.type == 'starred':
            return list(reversed(list(_lookup_playlist(web_session, config, uri))))
        else:
            logger.info(
                'Failed to lookup "%s": Cannot handle %r',
                uri, sp_link.type)
            return []
    except spotify.Error as exc:
        logger.info('Failed to lookup "%s": %s', uri, exc)
        return []


def _lookup_track(config, sp_link):
    sp_track = sp_link.as_track()
    sp_track.load(config['timeout'])
    track = translator.to_track(sp_track, bitrate=config['bitrate'])
    if track is not None:
        yield track


def _lookup_album(config, sp_link):
    sp_album = sp_link.as_album()
    sp_album_browser = sp_album.browse()
    sp_album_browser.load(config['timeout'])
    for sp_track in sp_album_browser.tracks:
        track = translator.to_track(
            sp_track, bitrate=config['bitrate'])
        if track is not None:
            yield track


def _lookup_artist(config, sp_link):
    sp_artist = sp_link.as_artist()
    sp_artist_browser = sp_artist.browse(
        type=spotify.ArtistBrowserType.NO_TRACKS)
    sp_artist_browser.load(config['timeout'])

    # Get all album browsers we need first, so they can start retrieving
    # data in the background.
    sp_album_browsers = []
    for sp_album in sp_artist_browser.albums:
        sp_album.load(config['timeout'])
        if not sp_album.is_available:
            continue
        if sp_album.type is spotify.AlbumType.COMPILATION:
            continue
        if sp_album.artist.link.uri in _VARIOUS_ARTISTS_URIS:
            continue
        sp_album_browsers.append(sp_album.browse())

    for sp_album_browser in sp_album_browsers:
        sp_album_browser.load(config['timeout'])
        for sp_track in sp_album_browser.tracks:
            track = translator.to_track(
                sp_track, bitrate=config['bitrate'])
            if track is not None:
                yield track


def _lookup_playlist(web_session, config, uri):
    web_playlist = web_session.get_playlist(uri)
    web_tracks = web_playlist.get('tracks', {}).get('items', [])
    for web_track in web_tracks:
        track = translator.web_to_track(web_track, bitrate=config['bitrate'])
        if track is not None:
            yield track