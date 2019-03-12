import requests
from pprint import pprint
from apscheduler.schedulers.background import BackgroundScheduler
import os
from app.scraper.scraper import Scraper
from flask import current_app, url_for
from flask_login import current_user
from urllib.parse import quote
from base64 import b64encode

from sqlalchemy import update, delete, and_

from sqlalchemy.exc import InternalError

from app import db
from app.models import Artist, ArtistNotInSpotify, ArtistSimilarity, ArtistToTag, ArtistToTrack, \
    Playlist, PlaylistTrack, Tag, Track, UserToArtist, UserToTrack, get

from datetime import datetime, timedelta
import click
from config import Config
import time
import json

from requests.exceptions import SSLError

class Spotify(Scraper):

    def __init__(self):
        self.name = "Spotify Scraper"

        # SETUP SCRAPER (non-user) Auth
        try:
            self.redirect_uri = url_for('auth.login', _external=True) +'?'
        except:
            self.redirect_uri = "http://localhost:5000/auth/login?"

        self.client_id = current_app.config["SPOTIFY_CLIENT_ID"]
        self.client_secret = current_app.config["SPOTIFY_CLIENT_SECRET"]
        self.spotify_localify_user_refresh_token = current_app.config["SPOTIFY_LOCALIFY_USER_REFRESH_TOKEN"]
        client_bytes = b64encode(str.encode(self.client_id+":"+self.client_secret))
        self.auth_str = 'Basic ' + client_bytes.decode()

        self.set_scraper_auth_info()
        self.set_localify_user_auth_info()

        scheduler = BackgroundScheduler()
        scheduler.add_job(self.set_scraper_auth_info, 'interval', minutes=59)
        scheduler.add_job(self.set_localify_user_auth_info, 'interval', minutes=59)
        scheduler.start()



    def set_scraper_auth_info(self):
        print("Fetching New Auth Tokens for Scraper")
        self.scraper_auth_info = requests.post(
            'https://accounts.spotify.com/api/token',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': self.auth_str}
            ,
            data={'grant_type': 'client_credentials'}
        )

        self.scraper_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer '+ self.scraper_auth_info.json()['access_token']
        }

    def set_localify_user_auth_info(self):
        print("Fetching New Auth Tokens for Localify User using refresh token")

        (access_token, expires_in) = self.refresh_access_token(self.spotify_localify_user_refresh_token)

        self.localify_user_access_token = access_token
        self.localify_user_access_token_expire_time = expires_in

        self.localify_user_headers =  {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.localify_user_access_token
        }

    def get_first_access_token(self, spotify_code):
        self.user_auth_info = requests.post(
            'https://accounts.spotify.com/api/token',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': self.auth_str
            },
            data={'grant_type': 'authorization_code',
                  'code': spotify_code,
                  'redirect_uri': self.redirect_uri
                  }
        )
        response = self.user_auth_info.json()
        expires_in = datetime.now() + timedelta(seconds=response['expires_in'])

        return (response['access_token'], response['refresh_token'], expires_in)


    def refresh_access_token(self, refresh_token):

        auth_info = requests.post(
            'https://accounts.spotify.com/api/token',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': self.auth_str
            },
            data={'grant_type': 'refresh_token',
                  'refresh_token': refresh_token,
                  }
        )
        response = auth_info.json()
        expires_in = datetime.now() + timedelta(seconds=response['expires_in'])

        return (response['access_token'], expires_in)

    def get_user_headers(self):

        if current_user.spotify_access_token_expire_time < datetime.now():
            (access_token, expires_in) = self.refresh_access_token(current_user.spotify_refresh_token)
            current_user.spotify_access_token = access_token
            current_user.spotify_access_token_expire_time = expires_in
            db.session.commit()

        return self.get_user_headers_from_access_token(current_user.spotify_access_token)


    def get_user_headers_from_access_token(self, access_token):

        return {
            'Content-Type': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer '+ access_token
        }

    def get_top_user_artists(self):

        user_headers = self.get_user_headers()
        top_artists = requests.get(
            "https://api.spotify.com/v1/me/top/artists",
            headers=user_headers,
            params={'time_range': 'medium_term',
                    'limit': 50}
        )
        taj = top_artists.json()

        if 'items' in taj:
            return taj['items']
        else:
            return None

    def update_top_user_artists(self, top_n_selected=24):
        """
        updates the user_to_artist relationships
        based on heavy rotations artists from Spotify
        :param top_n_selected: automatically sets first n artists to be
        selected by user, and removes any previous selections
        when spotify rank is above n.
        :return: list of artist objects

        """
        top_artists = self.get_top_user_artists()
        rank = 1
        artist_list = []

        # wipe out all existing scores and ranks
        q = update(UserToArtist).where(UserToArtist.user_id == current_user.id).values(spotify_rank=-1, spotify_score=0, score=0)
        db.session.execute(q)


        for spotify_artist in top_artists:
            sa_id = spotify_artist['id']
            a = Artist.query.filter(Artist.spotify_id==sa_id).first()
            if a is None:
                a = Artist(name=spotify_artist['name'], spotify_id=sa_id)
                db.session.add(a)
                db.session.commit()
                a = self._update_artist_details(a, spotify_artist)

            artist_list.append(a)

            u2a = get(UserToArtist, False, user_id=current_user.id, artist_id=a.id)

            if u2a is None:

                selected = False
                if rank <= top_n_selected:
                    selected = True

                u2a = UserToArtist(user_id=current_user.id,
                                   artist_id = a.id,
                                   created=datetime.now(),
                                   updated=datetime.now(),
                                   score=self._get_spotify_score(rank),
                                   spotify_score=self._get_spotify_score(rank),
                                   spotify_last_scraped=datetime.now(),
                                   spotify_first_scraped=datetime.now(),
                                   spotify_rank=rank,
                                   spotify_highest_rank=rank,
                                   selected=selected,
                                   recommendation_count=0)
                db.session.add(u2a)
                db.session.commit()

            else:
                if u2a.spotify_highest_rank is None or rank < u2a.spotify_highest_rank:
                    u2a.spotify_highest_rank = rank
                u2a.spotify_rank = rank
                u2a.spotify_score = self._get_spotify_score(rank)
                u2a.score = self._get_spotify_score(rank)
                u2a.spotify_last_scraped = datetime.utcnow()
                u2a.updated = datetime.utcnow()

                if u2a.selected is None:
                    if rank <= 24:
                        u2a.selected = True
                    else:
                        u2a.selected = False

                db.session.commit()
            rank +=1

        q = update(UserToArtist)\
            .where(and_(UserToArtist.user_id == current_user.id, UserToArtist.spotify_rank > top_n_selected))\
            .values(selected=0)
        db.session.execute(q)

        return artist_list

    def get_top_user_tracks(self):
        user_headers= self.get_user_headers()
        top_tracks = requests.get(
            "https://api.spotify.com/v1/me/top/tracks",
            headers=user_headers,
            params={'time_range': 'medium_term',
                    'limit': 50}
        )
        return top_tracks.json()['items']

    def update_top_user_tracks(self):
        top_tracks = self.get_top_user_tracks()
        track_list = []
        rank = 1

        q = update(UserToTrack).where(UserToTrack.user_id == current_user.id).values(spotify_rank=-1, spotify_score=0,
                                                                                     score=0)
        db.session.execute(q)

        for spotify_track in top_tracks:
            st_id = spotify_track['id']
            t = Track.query.filter(Track.spotify_id == st_id).first()
            if t is None:

                sa_id = spotify_track['artists'][0]['id']
                a = Artist.query.filter(Artist.spotify_id == sa_id).first()
                if a is None:
                    a = Artist(name=spotify_track['artists'][0]['name'], spotify_id=sa_id)
                    db.session.add(a)
                    db.session.commit()

                t = self._update_track_details(spotify_track)
                a2tr = get(ArtistToTrack, True, artist=a, track=t)


            track_list.append(t)

            u2t = get(UserToTrack, False, user_id=current_user.id, track_id=t.id)

            if u2t is None:

                u2t = UserToTrack(user_id=current_user.id,
                                   track_id = t.id,
                                   created=datetime.now(),
                                   updated=datetime.now(),
                                   score=self._get_spotify_score(rank),
                                   spotify_score=self._get_spotify_score(rank),
                                   spotify_last_scraped=datetime.now(),
                                   spotify_first_scraped=datetime.now(),
                                   spotify_rank=rank,
                                   spotify_highest_rank=rank,
                                   recommendation_count=0
                                  )
                db.session.add(u2t)
                db.session.commit()

            else:
                if rank < u2t.spotify_highest_rank:
                    u2t.spotify_highest_rank = rank
                u2t.spotify_rank = rank
                u2t.spotify_score = self._get_spotify_score(rank)
                u2t.score = self._get_spotify_score(rank)
                u2t.spotify_last_scraped = datetime.utcnow()
                u2t.updated = datetime.utcnow()

                db.session.commit()
            rank +=1


    def get_user_profile(self, access_code):
        user_headers= self.get_user_headers_from_access_token(access_code)
        user_profile = requests.get(
            "https://api.spotify.com/v1/me",
            headers=user_headers,
            params={}
        )
        pprint(user_profile.json())
        return user_profile.json()

    def create_playlist(self, name, description, share=True):
        user_id = str(current_user.spotify_id)
        localify_id = Config.SPOTIFY_LOCALIFY_USERNAME

        if user_id is None:
            print("ERROR-user id is none")
        url = 'https://api.spotify.com/v1/users/'+localify_id+'/playlists'
        #data = {"name": name,
        #        "public": "true",
        #        "collaborative": "false",
        #        "description": description}

        data = "{{\"name\":\"{}\",\"public\":true, \"collaborative\":false, \"description\":\"{}\"}}"\
            .format(name, description)
        user_headers = self.get_user_headers()

        playlist = requests.post(
            url,
            headers=self.localify_user_headers,
            data=data
        )

        playlist_json = playlist.json()

        url = "https://api.spotify.com/v1/playlists/"+playlist_json["id"]+"/followers"
        share = requests.put(
            url,
            headers=self.get_user_headers()
        )

        return playlist_json

    #use full playlist_uri, including user_id
    def add_to_playlist(self, track_ids, playlist_id):

        user_id = Config.SPOTIFY_LOCALIFY_USERNAME
        url = 'https://api.spotify.com/v1/users/'+user_id+'/playlists/'+playlist_id+'/tracks/'

        playlist = requests.post(
            url,
            headers=self.localify_user_headers,
            params={'uris': ','.join(track_ids)}
        )
        print("Added tracks to Spotify Playlist", playlist_id)

    def remove_all_tracks_from_playlist(self, playlist_id):


        url ='https://api.spotify.com/v1/playlists/'+playlist_id
        playlist = requests.get(
            url,
            headers=self.localify_user_headers
        )
        tracks = {"tracks":[]}
        for t in playlist.json()["tracks"]["items"]:
            tracks["tracks"].append({"uri":t['track']["uri"]})

        if len(tracks["tracks"]) == 0:
            return

        url = 'https://api.spotify.com/v1/playlists/' + playlist_id+"/tracks"
        playlist = requests.delete(
            url,
            headers=self.localify_user_headers,
            data=json.dumps(tracks)
        )
        print("All Tracks remove from playlist", playlist_id)



    def get_artist_by_name(self, name):
        """ has to be a perfect match between given name first artist returned from spotify"""

        artist_info = requests.get(
            'https://api.spotify.com/v1/search',
            headers = self.scraper_headers,
            params={'q': name, 'type': 'artist', 'limit': '1'}
        )

        if not artist_info.ok or len(artist_info.json()['artists']['items']) == 0:
            #print("ERROR: no spotify results for artist *"+name+"*")
            return None

        if name == artist_info.json()['artists']['items'][0]["name"]:
            return artist_info.json()['artists']['items'][0]
        else:
            return None

    def get_artist_by_id(self, id):

        artist_info = requests.get(
            'https://api.spotify.com/v1/artists/' + id,
            headers = self.scraper_headers,
            params={}
        )

        if not artist_info.ok or artist_info.json() == "":
            #print("ERROR: no spotify results for artist id *"+id+"*")
            return None
        return artist_info.json()

    def get_top_tracks_by_artist_id(self, artist_id):
        url = 'https://api.spotify.com/v1/artists/'+artist_id+'/top-tracks'
        top_tracks = requests.get(
            url,
            headers=self.scraper_headers,
            params={'country': 'US'}
        )
        if "tracks" in top_tracks.json():
            return top_tracks.json()['tracks']
        return None

    def get_tracks_audio_features_by_id(self, track_id):
        url = 'https://api.spotify.com/v1/audio-features/'+track_id
        audio_features = requests.get(
            url,
            headers=self.scraper_headers,
            params={'country': 'US'}
        )
        return audio_features.json()

    def get_related_artists_by_artist_id(self, artist_id):
        url = 'https://api.spotify.com/v1/artists/'+artist_id+'/related-artists'
        try:
            related_artists = requests.get(
                url,
                headers=self.scraper_headers,
                params={'country': 'US'}
            )
            related_artist_json = related_artists.json()
            if 'artists' not in related_artist_json:
                return None
            return related_artists.json()['artists']
        except requests.exceptions.RequestException as e:  # This is the correct syntax
            print("error for artist: "+str(artist_id))
            print(e)
            os.system('say "Spotify Error, Spotify Error, Spotify Error"')
            return

    def _parse_images(self, image_json, small_size_threshold=200, large_size_threshold=600):
        """ returns urls for small, medium, and large images"""
        small_medium_large = [ None,None, None]
        for image in image_json:
            h = image['height']
            w = image['width']
            if h < small_size_threshold and w < small_size_threshold:
                small_medium_large[0] = image['url']
            elif h > large_size_threshold and w > large_size_threshold:
                small_medium_large[2] = image['url']
            else:
                small_medium_large[1] = image['url']
        return small_medium_large


    def _update_artist_details(self, a, spotify_artist):

        a.name = spotify_artist["name"]
        a.spotify_id = spotify_artist["id"]
        a.spotify_popularity = spotify_artist["popularity"]


        for genre in spotify_artist["genres"]:
            genre_tag = get(Tag, True, name=genre)
            at2 = get(ArtistToTag, True, artist_id=a.id, tag_id=genre_tag.id)
            at2.spotify_score = 1
            if at2.score == 0:
                at2.score = 1

        image_list = self._parse_images(spotify_artist["images"])
        a.spotify_image_small_url =  image_list[0]
        a.spotify_image_medium_url = image_list[1]
        a.spotify_image_large_url = image_list[2]

        db.session.commit()
        return a

    def update_artist_information(self, a):

        try:
            if a.spotify_id is None:
                spotify_artist = self.get_artist_by_name(a.name)
            else:
                spotify_artist = self.get_artist_by_id(a.spotify_id)
        except SSLError:
            print("Error: No response from Spotify")
            return

        if spotify_artist is None:
            print("Artist",a.name,"not Found on Spotify")
            return

        a = self._update_artist_details(a, spotify_artist)
        return a

    def update_artist_top_tracks(self,a):
        if a.spotify_id is None:
            a = self.update_artist_information(a)
            if a is None:
                return
        try:
            spotify_tracks = self.get_top_tracks_by_artist_id(a.spotify_id)
        except:
            print("Error: Unable to get Spotify Top Tracks for artist: ", a.name, a.spotify_id)
            return
        if spotify_tracks is None:
            print("Warning: Spotify Top Tracks is None for artist: ", a.name, a.spotify_id)
            return

        for spotify_track in spotify_tracks:
            track = self._update_track_details(spotify_track)
            a2tr = get(ArtistToTrack, True, artist=a, track=track)


    def _update_track_details(self, spotify_track):

        track = get(Track, True, spotify_id=spotify_track["id"])
        track.spotify_id = spotify_track["id"]
        track.name = spotify_track['name']
        track.spotify_popularity = spotify_track['popularity']
        track.spotify_duration = spotify_track['duration_ms']
        track.spotify_explicit = spotify_track["explicit"]
        track.spotify_album_id = spotify_track['album']['id']
        track.spotify_album_name = spotify_track['album']['name']

        image_list = self._parse_images(spotify_track['album']["images"])
        track.spotify_image_small_url = image_list[0]
        track.spotify_image_medium_url = image_list[1]
        track.spotify_image_large_url = image_list[2]
        track.spotify_last_scraped = datetime.utcnow()

        if track.spotify_acousticness is None:  # skip audio feature request if info already in db

            try:
                features = self.get_tracks_audio_features_by_id(track.spotify_id)
            except SSLError:
                print("Error: Unable to get audio features for track: ", track.name, track.spotify_id)
                db.session.commit()  # commit track without audio features
                return track
            if "acousticness" in features:
                track.spotify_acousticness = features["acousticness"]
            if "danceability" in features:
                track.spotify_danceability = features["danceability"]
            if "energy" in features:
                track.spotify_energy = features["energy"]
            if "instrumentalness" in features:
                track.spotify_instrumentalness = features["instrumentalness"]
            if "key" in features:
                track.spotify_key = features["key"]
            if "liveness" in features:
                track.spotify_liveness = features["liveness"]
            if "loudness" in features:
                track.spotify_loudness = features["loudness"]
            if "mode" in features:
                track.spotify_mode = features["mode"]
            if "speechiness" in features:
                track.spotify_speechiness = features["speechiness"]
            if "tempo" in features:
                track.spotify_tempo = features["tempo"]
            if "time_signature" in features:
                track.spotify_time_signature = features["time_signature"]
            if "valence" in features:
                track.spotify_valence = features["valence"]

        db.session.commit()
        return track

    def _get_spotify_score(self, rank):
        score = 1.0
        decrease_amt = 0.025
        min_score = 0.25
        return max(score-rank*decrease_amt, min_score)

    def update_artist_similar_artists(self, a):

        if a.spotify_id is None:
            a = self.update_artist_information(a)
            if a is None:
                return

        rank = 1
        for spotify_similar_artist in self.get_related_artists_by_artist_id(a.spotify_id):

            #similar_artist = get(Artist, False, name=spotify_similar_artist["name"])

            # new code to prevent duplicate spotify artist who change spelling of name
            similar_artist = get(Artist, False, spotify_id=spotify_similar_artist["id"])
            if similar_artist is None:
                similar_artist = get(Artist, False, name=spotify_similar_artist['name'], spotify_id=None)

            if similar_artist is None:
                similar_artist = Artist(name=spotify_similar_artist['name'], spotify_id=spotify_similar_artist["id"])
                db.session.add(similar_artist)
                db.session.commit()

            similar_artist = self._update_artist_details(similar_artist, spotify_similar_artist)
            asim = get(ArtistSimilarity, True, seed_artist_id=a.id, similar_artist_id=similar_artist.id)
            asim.spotify_rank = rank
            asim.spotify_score = self._get_spotify_score(rank)
            if asim.score == 0:
                asim.score = asim.spotify_score
            db.session.commit()

            if Config.ADD_SYMMETRIC_SIMILARITY:
                asim_rev = get(ArtistSimilarity, True, seed_artist_id=similar_artist.id, similar_artist_id=a.id)
                if asim_rev.spotify_rank is None:
                    asim_rev.spotify_rank = -rank
                new_score = Config.SYMMETRIC_SIMILARITY_DISCOUNT * asim.spotify_score
                if asim_rev.spotify_score is None or asim_rev.spotify_score < new_score:
                    asim_rev.spotify_score = new_score
                if asim_rev.score == 0 or asim_rev.score < new_score:
                    asim_rev.score = new_score

                db.session.commit()
            rank += 1

    def update_artist(self, a):
        #print("Updating artist: ", a.name, end="")
        #print(" Artist Info...", end="")
        self.update_artist_information(a)
        #print(" Top Tracks...", end="")
        self.update_artist_top_tracks(a)
        #print(" Similar Artists...", end="")
        self.update_artist_similar_artists(a)
        a.spotify_last_scraped = datetime.utcnow()
        db.session.commit()
        #print(" done.")

    def lookup_artist(self, name, last_n_days=90):
        """
        looks up artists object if it already exists, creates it if found in spotify,
        returns none if not found and not in spotify
        :param name: name string of artist
        :return: Artist db object if it already exists, None otherwise
        """

        # returns Artist object if it already exists
        artist_obj = get(Artist, False, name=name)
        if artist_obj is not None:
            return artist_obj

        # see if artist string has already been cached from previous spotify request
        since = datetime.utcnow() - timedelta(days=last_n_days)
        anis = get(ArtistNotInSpotify, False, name=name)

        if anis is None or anis.spotify_last_scraped is None or anis.spotify_last_scraped < since:
            artist_json = self.get_artist_by_name(name)

            if artist_json is not None:

                # If artist changed name but still has a spotify id
                artist_obj = get(Artist, False, spotify_id=artist_json["id"])
                if artist_obj is not None:
                    artist_obj.name = artist_json["name"]
                    artist_obj.spotify_popularity = artist_json["popularity"]
                    db.session.commit()
                    return artist_obj

                a = Artist(name=artist_json["name"], spotify_id=artist_json["id"])
                db.session.add(a)
                db.session.commit()
                self.update_artist(a)
                return get(Artist, False, spotify_id=artist_json["id"])
            else:
                try:
                    anis = get(ArtistNotInSpotify, True, name=name)
                    anis.spotify_last_scraped = datetime.utcnow()
                    db.session.commit()
                    return None
                except InternalError:
                    print("SQLAlchemy Internal Error: ", name, "not a valid character set")
                    return None

        return None


def driver():
    click.echo("HELLO SCRAPER")
    spotify = Spotify()
    pprint(spotify.auth_info)
    artist_name = "the strokes"
    spotify_artist = spotify.get_artist_by_name(artist_name)
    pprint(spotify_artist)
    #related_artists = spotify.get_related_artists_by_artist_id(spotify_artist['id'])
    #pprint(related_artists)
    #click.echo("end of Spotify scraper driver")
    pass


if __name__ == '__main__':
    driver()

