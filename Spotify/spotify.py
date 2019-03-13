import requests

GET_ME_PLAYLIST_ENDPOINT = 'https://api.spotify.com/v1/me/playlists'
GET_PLAYLIST_ENDPOINT = ''
GET_USER = 'https://api.spotify.com/v1/users/{user_id}'
GET_CURRENT = 'https://api.spotify.com/v1/me'


def getPlaylists():
    url = GET_PLAYLIST_ENDPOINT
    resp = requests.get(url)
    return resp.json()


def getUser():
    # url = GET_USER.format(user_id='birdforceone')
    url = GET_CURRENT
    resp = requests.get(url)
    return resp.json()


def main():
    print(getUser())


if __name__ == "__main__":
    main()
