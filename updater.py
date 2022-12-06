import json
import spotipy
import logging
import datetime
from spotipy.oauth2 import SpotifyOAuth
from spotipy import SpotifyException

LIKED_SONGS_TYPE = 'liked_songs'
PLAYLIST_TYPE = 'playlist'

scope = "user-library-read,playlist-modify-public,playlist-modify-private"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
current_user_id = sp.current_user()['id']

class Track:
    def __init__(self, id, name, added_at):
        self.id = id
        self.name = name
        self.added_at = added_at

class Playlist:
    def __init__(self, id, name, tracks):
        self.id = id
        self.name = name
        self.tracks = tracks

class PlaylistRepository:
    def get_playlist_from_config(self, playlist_to_mirror_config):
        playlist = sp.playlist(playlist_to_mirror_config['id'])
        return Playlist(
            playlist['id'],
            playlist['name'],
            self._get_tracks_from_playlist(playlist))
            
    def get_playlists_with_name(self, name):
        playlists = sp.current_user_playlists()['items']
        return [
            Playlist(
                playlist['id'],
                playlist['name'],
                self._get_tracks_from_playlist(sp.playlist(playlist['id']))
            ) 
            for playlist 
            in filter(lambda p: p['name'] == name, playlists)
        ]
    
    def get_or_create_playlist_with_name(self, name):
        playlists = self.get_playlists_with_name(name)
        if len(playlists) > 0:
            print("Playlist with name {} exists".format(name))
            return playlists
        print("Playlist with name {} doesn't exist. Creating new one".format(name))
        created_playlist_json = sp.user_playlist_create(current_user_id, name)
        return [Playlist(
            created_playlist_json['id'],
            name,
            []
        )]

    def get_liked_songs():
        saved_tracks = sp.current_user_saved_tracks()
        return Playlist(
            saved_tracks['id'],
            'Liked Songs',
            [item['track']['id'] for item in saved_tracks['items']])

    def _get_tracks_from_playlist(self, playlist):
        return [
            Track(item['track']['id'], item['track']['name'], item['added_at']) 
            for item 
            in playlist['tracks']['items']]

class CopyPlaylistFactory:
    def create_playlist(self, original_playlist, playlist_config) -> Playlist:
        pass

class CopyTracksFromDatePlaylistFactory(CopyPlaylistFactory):
    def create_playlist(self, original_playlist, playlist_config):
        from_date = playlist_config['from_date']
        tracks = self.get_tracks_from_date(original_playlist, from_date)
        return Playlist(None, "{} [from {}]".format(original_playlist.name, from_date), tracks)

    def get_tracks_from_date(self, original_playlist, date):
        sorted_tracks = sorted(original_playlist.tracks, key=lambda t: t.added_at)
        return [track for track in sorted_tracks if track.added_at >= date]

class CopyNumRecentTracksPlaylistFactory(CopyPlaylistFactory):
    def create_playlist(self, original_playlist, playlist_config):
        count = playlist_config['most_recent_count']
        if count is None:
            raise Exception(
                "Can't create Playlist from this configuration. Missing `count` key: {}".format(playlist_config))
        recent_tracks = self.get_recent_tracks(original_playlist, count)
        return Playlist(None, "{} [last {}]".format(original_playlist.name, count), recent_tracks)
    
    def get_recent_tracks(self, original_playlist, count):
        return sorted(original_playlist.tracks, key=lambda t: t.added_at)[-count:]



for config in [
    {
        "type": "playlist",
        # "id": "3OI8krl8FxMZsyzJSa8LUM",
        # "id": "6YWdIfKcfus3hSjtpZKngh",
        "id": "0nGiC07XVUxBqOGd407pBO",
        # "from_date": "2022-06-23",
        "most_recent_count": 112
    }]:
    playlist_repository = PlaylistRepository()
    if config['type'] == LIKED_SONGS_TYPE:
        original_playlist = playlist_repository.get_liked_songs()
    elif config['type'] == PLAYLIST_TYPE:
        original_playlist = playlist_repository.get_playlist_from_config(config)
    else:
        raise Exception("Unrecognized type")

    if 'from_date' in config:
        factory = CopyTracksFromDatePlaylistFactory()
    elif 'most_recent_count' in config:
        factory = CopyNumRecentTracksPlaylistFactory()
    else:
        raise Exception("No strategy for copy in config: {}".format(config))
    mirror_playlist = factory.create_playlist(original_playlist, config)
    playlists = playlist_repository.get_or_create_playlist_with_name(mirror_playlist.name)
    if len(playlists) > 1:
        raise Exception("More than one playlist with the name of the mirror playlist")
    if len(playlists) == 0:
        raise Exception("Playlist not created")
    playlist_to_populate = playlists[0]
    sp.user_playlist_remove_all_occurrences_of_tracks(
        current_user_id,
        playlist_to_populate.id, 
        [t.id for t in playlist_to_populate.tracks])
    print(len(mirror_playlist.tracks))
    for t in range(0, len(mirror_playlist.tracks), 100):
        print("HEY: {}".format([t.id for t in mirror_playlist.tracks[t:100]]))
    sp.user_playlist_add_tracks(current_user_id, playlist_to_populate.id, [t.id for t in mirror_playlist.tracks])
    # if len(existing_playlists) == 1:
    #     print("Playlist with name {} exists, deleting existing tracks".format(copy_playlist.name))
    #     existing_playlist = existing_playlists[0]
    #     for track in existing_playlist.tracks:
    #         print("Removing track: ({}, {}), added at:{}".format(track.name, track.id, track.added_at))
    #     sp.user_playlist_remove_all_occurrences_of_tracks(sp.current_user(), existing_playlist.id, existing_playlist.tracks) 
    
    # use copy_playlist_id to add tracks to it.
