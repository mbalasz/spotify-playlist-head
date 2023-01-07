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

class TracksFromDateCopyPlaylistFactory(CopyPlaylistFactory):
    def __init__(self, from_date):
        self.from_date = from_date

    def create_playlist(self, original_playlist, playlist_config):
        tracks = self.get_tracks_from_date(original_playlist, self.from_date)
        return Playlist("{} [from {}]".format(original_playlist.name, self.from_date), tracks)

    def get_tracks_from_date(self, original_playlist, date):
        # TODO add logic
        pass

class NumRecentTracksCopyPlaylistFactory(CopyPlaylistFactory):
    def __init__(self, num_recent_tracks):
        self.num_recent_tracks = num_recent_tracks

    def create_playlist(self, original_playlist, playlist_config):
        recent_tracks = self._get_recent_tracks(original_playlist, self.num_recent_tracks)
        return Playlist("{} [last {}]".format(original_playlist.name, self.num_recent_tracks), recent_tracks)
    
    def _get_recent_tracks(self, original_playlist, count):
        return sorted(original_playlist.tracks, key=lambda t: t.added_at)[-count:]

for config in [
    {
        "type": "playlist",
        # "id": "3OI8krl8FxMZsyzJSa8LUM",
        "id": "0nGiC07XVUxBqOGd407pBO",
        # "id": "6YWdIfKcfus3hSjtpZKngh",
        "num_recent_tracks": 212
        # "from_date": "2019-01-01"
    }]:
    if config['type'] == LIKED_SONGS_TYPE:
        playlist_fetcher = LikedSongsFetcher()
    elif config['type'] == PLAYLIST_TYPE:
        playlist_fetcher = RegularPlaylistFetcher()
    else:
        raise Exception("Unrecognized type")
    original_playlist = playlist_fetcher.fetch(config)

    if 'from_date' in config:
        factory = TracksFromDateCopyPlaylistFactory(config['from_date'])
    elif 'num_recent_tracks' in config:
        factory = NumRecentTracksCopyPlaylistFactory(config['num_recent_tracks'])
    else:
        raise Exception("No strategy for copy in config: {}".format(config))
    copy_playlist = factory.create_playlist(original_playlist, config)

    existing_playlists = RegularPlaylistFetcher().fetch_with_name(copy_playlist.name)
    if len(existing_playlists) == 1:
        print("Playlist with name {} exists, deleting existing tracks".format(copy_playlist.name))
        existing_playlist = existing_playlists[0]
        tracks_to_remove = [
            track 
            for track 
            in existing_playlist.tracks 
            if track.id not in [copy_track.id for copy_track in copy_playlist.tracks]]
        tracks_to_add = [
            track
            for track
            in copy_playlist.tracks
            if track.id not in [existing_track.id for existing_track in existing_playlist.tracks]
        ]

        for track in tracks_to_remove:
            print("Removing track: ({}, {}), added at:{}".format(track.name, track.id, track.added_at))
        for track in tracks_to_add:
            print("Adding track: ({}, {}), added at:{}".format(track.name, track.id, track.added_at))
    elif len(existing_playlists) == 0:
        print("Playlist with name {} doesn't exist, will create new one".format(copy_playlist.name))
        print("Adding {} tracks".format(len(copy_playlist.tracks)))
    else:
        raise Exception("More than one playlist with the name of the copy playlist")
    # use copy_playlist_id to add tracks to it.
