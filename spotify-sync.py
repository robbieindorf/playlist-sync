import re
import time
import logging

import requests
from plexapi.server import PlexServer
from plexapi.audio import Track
import spotipy
import os
from spotipy.oauth2 import SpotifyClientCredentials
from typing import List


def filterPlexArray(plexItems=[], song="", artist="") -> List[Track]:
    for item in list(plexItems):
        if type(item) is not Track:
            plexItems.remove(item)
            continue
        if item.title.lower() != song.lower():
            plexItems.remove(item)
            continue
        artistItem = item.artist()
        if artistItem.title.lower() != artist.lower():
            plexItems.remove(item)
            continue

    return plexItems


def getSpotifyPlaylist(sp: spotipy.client, playlistId: str) -> []:
    playlist = sp.playlist(playlistId)
    return playlist


# Returns a list of spotify playlist objects
def getSpotifyUserPlaylists(sp: spotipy.client, userId: str) -> []:
    playlists = sp.user_playlists(userId)
    spotifyPlaylists = []
    while playlists:
        playlistItems = playlists['items']
        for i, playlist in enumerate(playlistItems):
            if playlist['owner']['id'] == userId:
                spotifyPlaylists.append(getSpotifyPlaylist(sp, userId, playlist['id']))
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            playlists = None
    return spotifyPlaylists


def getSpotifyTracks(sp: spotipy.client, playlist: []) -> []:
    spotifyTracks = []
    tracks = playlist['tracks']
    spotifyTracks.extend(tracks['items'])
    while tracks['next']:
        tracks = sp.next(tracks)
        spotifyTracks.extend(tracks['items'])
    return spotifyTracks


def getPlexTracks(plex: PlexServer, spotifyTracks: []) -> List[Track]:
    plexTracks = []
    for spotifyTrack in spotifyTracks:
        if spotifyTrack['track'] == None:
            continue
        track = spotifyTrack['track']

        try:
            musicTracks = plex.search(track['artist'], mediatype='artist')
        except:
            try:
                musicTracks = plex.search(track['name'], mediatype='artist')
            except:
                logging.info("Issue making plex request")
                continue

        if len(musicTracks) > 0:
            plexMusic = filterPlexArray(musicTracks, track['name'], track['artists'][0]['name'])
            if len(plexMusic) > 0:
                plexTracks.append(plexMusic[0])
            else:
                logging.info("Missing Plex Song: %s by %s" % (track['name'], track['artists'][0]['name']))

    return plexTracks


def createPlaylist(plex: PlexServer, sp: spotipy.Spotify, playlist: []):
    playlistName = playlist['name']
    logging.info('Starting playlist %s' % playlistName)
    plexTracks = getPlexTracks(plex, getSpotifyTracks(sp, playlist))
    if len(plexTracks) > 0:
        try:
            plexPlaylist = plex.playlist(playlistName)
            logging.info('Updating playlist %s' % playlistName)
            plexPlaylist.addItems(plexTracks)
        except:
            logging.info("Creating playlist %s" % playlistName)
            plex.createPlaylist(playlistName, plexTracks)

def parseSpotifyURI(uriString: str) -> {}:
    spotifyUriStrings = re.sub(r'^spotify:', '', uriString).split(":")
    logging.info(spotifyUriStrings)
    spotifyUriParts = {}
    for i, string in enumerate(spotifyUriStrings):
        if i % 2 == 0:
            spotifyUriParts[spotifyUriStrings[i]] = spotifyUriStrings[i+1]

    return spotifyUriParts


def runSync(plex : PlexServer, sp : spotipy.Spotify):
    logging.info('Starting a Sync Operation')
    playlists = []
    spotifyMainUris = []
    req = requests.get(os.environ.get('CONFIG_URL'))
    for line in req.text.splitlines():
        if re.match("-", line):
            continue
        spotifyUriParts = parseSpotifyURI(line)
        spotifyMainUris.append(spotifyUriParts)

    if spotifyMainUris is None:
        logging.error("No spotify uris")

    for spotifyUriParts in spotifyMainUris:
        if 'user' in spotifyUriParts.keys() and 'playlist' not in spotifyUriParts.keys():
            logging.info('Getting playlists for %s' % spotifyUriParts['user'])
            playlists.extend(getSpotifyUserPlaylists(sp, spotifyUriParts['user']))
        elif 'playlist' in spotifyUriParts.keys():
            logging.info('Getting playlist %s ' % spotifyUriParts['playlist'])
            playlists.append(getSpotifyPlaylist(sp, spotifyUriParts['playlist']))

    for playlist in playlists:
        createPlaylist(plex, sp, playlist)
    logging.info('Finished a Sync Operation')

def main():
    logging.basicConfig(level=logging.INFO)
    secondsToWait = int(os.environ.get('SECONDS_TO_WAIT', 1800))
    baseurl = os.environ.get('PLEX_URL')
    token = os.environ.get('PLEX_TOKEN')
    while True:
        plex = PlexServer(baseurl, token)
        client_credentials_manager = SpotifyClientCredentials()
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        runSync(plex, sp)
        time.sleep(secondsToWait)

if __name__ == '__main__':
    main()