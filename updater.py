import json
import spotipy
import logging
import datetime
from spotipy.oauth2 import SpotifyOAuth
from spotipy import SpotifyException
import traceback

LIKED_SONGS_TYPE = 'liked-songs'
PLAYLIST_TYPE = 'playlist'

scope = "user-library-read,playlist-modify-public,playlist-modify-private"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
current_user_id = sp.current_user()['id']

class Track:
    def __init__(self, id, name, added_at):
        self.id = id
        self.name = name
        self.added_at = added_at

def spotipy_item_to_track(item):
    return Track(item['track']['id'], item['track']['name'], item['added_at'])

def spotipy_items_to_tracks(items):
    return [
        spotipy_item_to_track(item)
        for item
        in items
    ]

class Playlist:
    def __init__(self, id, name, tracks):
        self.id = id
        self.name = name
        self.tracks = tracks

class PlaylistRepository:
    def get_playlist_from_config(self, playlist_to_mirror_config):
        playlist = sp.user_playlist(current_user_id, playlist_to_mirror_config['id'])
        return Playlist(
            playlist['id'],
            playlist['name'],
            self._get_tracks_from_playlist(playlist['name'], playlist['tracks']))
            
    def get_playlists_with_name(self, name):
        existing_playlists = sp.current_user_playlists()['items']
        return [
            Playlist(
                playlist['id'],
                playlist['name'],
                self._get_tracks_from_playlist(playlist['name'], sp.playlist(playlist['id'])['tracks'])
            ) 
            for playlist 
            in filter(lambda p: p['name'] == name, existing_playlists)
        ]
    
    def get_or_create_playlist_with_name(self, name):
        existing_playlists = self.get_playlists_with_name(name)
        if len(existing_playlists) > 0:
            print("Playlist with name {} exists".format(name))
            return existing_playlists
        print("Playlist with name {} doesn't exist. Creating new one".format(name))
        created_playlist_json = sp.user_playlist_create(current_user_id, name)
        return [Playlist(
            created_playlist_json['id'],
            name,
            []
        )]

    def get_liked_songs(self):
        saved_tracks = sp.current_user_saved_tracks(limit=50)
        return Playlist(
            None,
            'Liked Songs',
            self._get_tracks_from_playlist("Liked songs", saved_tracks)
        )

    def _get_tracks_from_playlist(self, playlist_name, playlist_tracks):
        result = spotipy_items_to_tracks(playlist_tracks['items'])
        while playlist_tracks['next']:
            print("Fetched {} tracks from {}".format(len(result), playlist_name))
            playlist_tracks = sp.next(playlist_tracks)
            result.extend(spotipy_items_to_tracks(playlist_tracks['items']))
        return result

class CopyPlaylistFactory:
    def create_playlist(self, original_playlist) -> Playlist:
        pass

class TracksFromDateCopyPlaylistFactory(CopyPlaylistFactory):
    def __init__(self, from_date):
        self.from_date = from_date

    def create_playlist(self, original_playlist):
        tracks = self.get_tracks_from_date(original_playlist, self.from_date)
        return Playlist(None, "{} [from {}]".format(original_playlist.name, self.from_date), tracks)

    def get_tracks_from_date(self, original_playlist, date):
        # TODO add logic
        pass

class NumRecentTracksCopyPlaylistFactory(CopyPlaylistFactory):
    def __init__(self, num_recent_tracks):
        self.num_recent_tracks = num_recent_tracks

    def create_playlist(self, original_playlist):
        recent_tracks = self._get_recent_tracks(original_playlist, self.num_recent_tracks)
        return Playlist(None, "{} [last {}]".format(original_playlist.name, self.num_recent_tracks), recent_tracks)
    
    def _get_recent_tracks(self, original_playlist, count):
        tracks = sorted(original_playlist.tracks, key=lambda t: t.added_at)[-count:]
        tracks.reverse()
        return tracks

for config in [
    {
        # "type": "playlist",
        "type": "liked-songs",
        # "id": "3OI8krl8FxMZsyzJSa8LUM",
        "num_recent_tracks": 800
        # "from_date": "2019-01-01"
    }]:
    playlist_repository = PlaylistRepository()
    if config['type'] == LIKED_SONGS_TYPE:
        original_playlist = playlist_repository.get_liked_songs()
    elif config['type'] == PLAYLIST_TYPE:
        original_playlist = playlist_repository.get_playlist_from_config(config)
    else:
        raise Exception("Unrecognized type")

    if 'from_date' in config:
        factory = TracksFromDateCopyPlaylistFactory(config['from_date'])
    elif 'num_recent_tracks' in config:
        factory = NumRecentTracksCopyPlaylistFactory(config['num_recent_tracks'])
    else:
        raise Exception("No strategy for copy in config: {}".format(config))
    mirror_playlist = factory.create_playlist(original_playlist)

    existing_playlists = playlist_repository.get_or_create_playlist_with_name(mirror_playlist.name)
    if len(existing_playlists) > 1:
        raise Exception("More than one playlist with the name of the mirror playlist already exists")
    if len(existing_playlists) == 0:
        raise Exception("Mirror playlist not created")
    playlist_to_populate = existing_playlists[0]
    tracks_to_remove = [
        track 
        for track 
        in playlist_to_populate.tracks 
        if track.id not in [mirror_track.id for mirror_track in mirror_playlist.tracks]]
    tracks_to_add = [
        (idx, track)
        for idx, track
        in enumerate(mirror_playlist.tracks)
        if track.id not in [existing_track.id for existing_track in playlist_to_populate.tracks]
    ]

    print("Removing {} tracks.".format(len(tracks_to_remove)))
    print("Adding {} tracks.".format(len(tracks_to_add)))
    for track in tracks_to_remove:
        print("Removing track: ({}, {}), added at:{}".format(track.name, track.id, track.added_at))
    for idx, track in tracks_to_add:
        print("Adding track: ({}, {}), added at:{}".format(track.name, track.id, track.added_at))
    sp.user_playlist_remove_all_occurrences_of_tracks(
        current_user_id,
        playlist_to_populate.id, 
        [track.id for track in tracks_to_remove])

    if len(tracks_to_add) > 0:
        # Adding tracks in batches with consecutive indices to preserve the same ordering of tracks.
        first_track_in_batch_idx = 0
        for i in range(1, len(tracks_to_add)):
            if tracks_to_add[i][0] - tracks_to_add[i-1][0] > 1 or i - first_track_in_batch_idx >= 100:
                sp.user_playlist_add_tracks(
                    current_user_id,
                    playlist_to_populate.id,
                    [track.id for idx, track in tracks_to_add[first_track_in_batch_idx:i]],
                    position = tracks_to_add[first_track_in_batch_idx][0])
                first_track_in_batch_idx = i

        sp.user_playlist_add_tracks(
            current_user_id,
            playlist_to_populate.id,
            [track.id for idx, track in tracks_to_add[first_track_in_batch_idx:len(tracks_to_add)]],
            position = tracks_to_add[first_track_in_batch_idx][0])
