#! /opt/homebrew/bin/ python3

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests, time, json, subprocess, os

opts = Options()
opts.add_extension("./ublockorigin.crx")
opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(
    options=opts,
)

driver.maximize_window()

# url = "https://www.twitch.tv/videos/1829719652"
# driver.get(url)
driver.get("https://www.twitch.tv/")
input("Continue when navigated to the VOD page with devtools open:")


XPATHS = {
    "settings": '//button[@aria-label="Settings"]',
    "quality": '//button[@data-a-target="player-settings-menu-item-quality"]',
    "source": '//div[contains(text(), "Source")]',
    "duration": '//p[@data-a-target="player-seekbar-duration"]',
    "title": '//*[@data-a-target="stream-title"]',
}

settings = driver.find_element("xpath", XPATHS["settings"])
settings.click()
quality = driver.find_element("xpath", XPATHS["quality"])
quality.click()
source = driver.find_element("xpath", XPATHS["source"])
source.click()

downurl = None
while not downurl:
    time.sleep(1)
    perf = driver.get_log("performance")
    print(len(perf), "logs")
    for log in perf:
        log = log["message"]

        # if "chunked" in log and ".m3u8" in log:
        #     headers = json.loads(log)["message"]["params"]["headers"]
        #     plist = headers[":authority"] + headers[":path"]
        #     plist = "https://" + plist[: plist.rfind("/")]

        if "chunked" in log and ".ts" in log:
            headers = json.loads(log)["message"]["params"]["headers"]
            downurl = headers[":authority"] + headers[":path"]
            downurl = "https://" + downurl[: downurl.rfind("/")]
            print(downurl)
            break

title = driver.find_element("xpath", XPATHS["title"])
title = title.text
print(f"{title=}")

duration = driver.find_element("xpath", XPATHS["duration"])
duration = float(duration.get_attribute("data-a-value"))

driver.close()


def get_nchunks():
    def check(n):
        return requests.head(f"{downurl}/{n}.ts").status_code == 200

    l, r = 0, int(duration)
    while l < r:
        print(l, r)
        m = (r + l) // 2
        a, b = check(m), check(m + 1)
        if b:
            l = m
        elif not a:
            r = m + 1
        else:
            return m
    else:
        print("something fucky going on")


nchunks = get_nchunks()
print(f"{nchunks=}")

cmd_curl = f' curl -Z --parallel-immediate --parallel-max 5000 --create-dirs  -C - "{downurl}/[1-{nchunks}].ts" -o "./chunks/#1.ts" '
subprocess.run(cmd_curl, shell=True)

# Get muted parts
muted = []
for file in os.listdir("./chunks"):
    if (
        file.endswith(".ts")
        and os.path.getsize(os.path.join("./chunks", file)) < 1000_000  # 1MB
    ):
        muted.append(file[:-3])
if muted:
    muted = "{" + ",".join(muted) + "}"
    cmd_curl = f' curl -Z --parallel-immediate --create-dirs -C - "{downurl}/{muted}-muted.ts" -o "./chunks/#1.ts" '
    subprocess.run(cmd_curl, shell=True)

# ffmpeg
with open("files.txt", "w") as fp:
    text = "\n".join(f"file './chunks/{i}.ts'" for i in range(1, nchunks))
    fp.write(text)
cmd_ffmpeg = f'ffmpeg -safe 0 -f concat -i files.txt -c copy "{title}.mp4" '
subprocess.run(cmd_ffmpeg, shell=True)

# # convert to 120fps
# if input("Convert to 120fps? [Y/n]") in ["y", "Y", ""]:
#     cmd_ffmpeg = f"ffmpeg -itsscale 0.5 -i {title}.mp4 -c:v copy -filter:a atempo=2.0 -b:a 160k {title}-120fps.mp4"
#     subprocess.run(cmd_ffmpeg, shell=True)

# cleanup
if input("Cleanup? ") in ["y", "Y", ""]:
    subprocess.run("rm -r chunks files.txt", shell=True)
