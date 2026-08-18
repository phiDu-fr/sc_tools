def play_mp3(soundtouch_ip, media_server_ip, mp3_path, title="Podcast"):
    import json
    import base64
    import requests

    mp3_url = f"http://{media_server_ip}{mp3_path}"

    data = {
        "name": title,
        "imageUrl": "",
        "streamUrl": mp3_url
    }

    b64 = base64.b64encode(
        json.dumps(data, separators=(',', ':')).encode()
    ).decode()

    orion_url = (
        f"http://{media_server_ip}:8000"
        f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"
    )

    def play_mp3(soundtouch_ip, media_server_ip, mp3_path, title="Podcast"):
    import json
    import base64
    import requests

    mp3_url = f"http://{media_server_ip}{mp3_path}"

    data = {
        "name": title,
        "imageUrl": "",
        "streamUrl": mp3_url
    }

    b64 = base64.b64encode(
        json.dumps(data, separators=(',', ':')).encode()
    ).decode()

    orion_url = (
        f"http://{media_server_ip}:8000"
        f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"
    )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ContentItem source="LOCAL_INTERNET_RADIO"
             type="stationurl"
             location="{orion_url}">
    <itemName>{title}</itemName>
</ContentItem>"""

    return requests.post(
        f"http://{soundtouch_ip}:8090/select",
        data=xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"}
    )

    return requests.post(
        f"http://{soundtouch_ip}:8090/select",
        data=xml,
        headers={"Content-Type": "text/xml"}
    )

# Exemple
play_mp3(
    soundtouch_ip="192.168.1.65",
    media_server_ip="192.168.1.116",
    mp3_path="/local_podcast/podcast.mp3",
    title="Mon Podcast"
)