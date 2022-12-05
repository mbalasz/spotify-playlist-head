import json
import spotipy
import logging
import datetime
from spotipy.oauth2 import SpotifyOAuth
from spotipy import SpotifyException

LIKED_SONGS_TYPE = 'liked_songs'
PLAYLIST_TYPE = 'playlist'

scope = "user-library-read"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

class Track:
    def __init__(self, id, name, added_at):
        self.id = id
        self.name = name
        self.added_at = added_at

class Playlist:
    def __init__(self, name, tracks):
        self.name = name
        self.tracks = tracks

class PlaylistFetcher:
    def fetch(self, playlist_to_mirror_config) -> Playlist:
        pass

    def fetch_with_name(self, name) -> [Playlist]:
        pass

class RegularPlaylistFetcher(PlaylistFetcher):
    def fetch(self, playlist_to_mirror_config):
        playlist = sp.playlist(playlist_to_mirror_config['id'])
        return Playlist(
            playlist['name'],
            self._get_tracks_from_playlist(playlist))
    
    def fetch_with_name(self, name):
        playlists = sp.current_user_playlists()['items']
        return [
            Playlist(
                playlist['name'],
                self._get_tracks_from_playlist(sp.playlist(playlist['id']))
            ) 
            for playlist 
            in filter(lambda p: p['name'] == name, playlists)
        ]


    def _get_tracks_from_playlist(self, playlist):
        return [
            Track(item['track']['id'], item['track']['name'], item['added_at']) 
            for item 
            in playlist['tracks']['items']]


class LikedSongsFetcher(PlaylistFetcher):
    def fetch(self, playlist_to_mirror_config):
        saved_tracks = sp.current_user_saved_tracks()
        return Playlist(
            'Liked Songs',
            [item['track']['id'] for item in saved_tracks['items']])

class CopyPlaylistFactory:
    def create_playlist(self, original_playlist, playlist_config) -> Playlist:
        pass

class CopyTracksFromDatePlaylistFactory(CopyPlaylistFactory):
    def create_playlist(self, original_playlist, playlist_config):
        from_date = playlist_config['from_date']
        tracks = self.get_tracks_from_date(original_playlist, from_date)
        return Playlist("{} [from {}]".format(original_playlist.name, from_date), tracks)

    def get_tracks_from_date(self, original_playlist, date):
        pass

class CopyNumRecentTracksPlaylistFactory(CopyPlaylistFactory):
    def create_playlist(self, original_playlist, playlist_config):
        count = playlist_config['most_recent_count']
        if count is None:
            raise Exception(
                "Can't create Playlist from this configuration. Missing `count` key: {}".format(playlist_config))
        recent_tracks = self.get_recent_tracks(original_playlist, count)
        return Playlist("{} [last {}]".format(original_playlist.name), recent_tracks)
    
    def get_recent_tracks(self, original_playlist, count):
        return sorted(original_playlist.tracks, key=lambda t: t.date_added)[-count:]



for config in [
    {
        "type": "playlist",
        # "id": "3OI8krl8FxMZsyzJSa8LUM",
        "id": "6YWdIfKcfus3hSjtpZKngh",
        "from_date": "2019-01-01"
    }]:
    if config['type'] == LIKED_SONGS_TYPE:
        playlist_fetcher = LikedSongsFetcher()
    elif config['type'] == PLAYLIST_TYPE:
        playlist_fetcher = RegularPlaylistFetcher()
    else:
        raise Exception("Unrecognized type")
    original_playlist = playlist_fetcher.fetch(config)

    if 'from_date' in config:
        factory = CopyTracksFromDatePlaylistFactory()
    elif 'most_recent_count' in config:
        factory = CopyNumRecentTracksPlaylistFactory()
    else:
        raise Exception("No strategy for copy in config: {}".format(config))
    copy_playlist = factory.create_playlist(original_playlist, config)

    existing_playlists = RegularPlaylistFetcher().fetch_with_name(copy_playlist.name)
    if len(existing_playlists) == 1:
        print("Playlist with name {} exists, deleting existing tracks".format(copy_playlist.name))
        existing_playlist = existing_playlists[0]
        for track in existing_playlist.tracks:
            print("Removing track: ({}, {}), added at:{}".format(track.name, track.id, track.added_at))
    elif len(existing_playlists) == 0:
        print("Playlist with name {} doesn't exist, will create new one".format(copy_playlist.name))
    else:
        raise Exception("More than one playlist with the name of the copy playlist")
    # use copy_playlist_id to add tracks to it.
