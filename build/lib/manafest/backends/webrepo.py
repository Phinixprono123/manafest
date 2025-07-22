name = "webrepo"
supported_os = ("linux","macos","windows")
actions = ("search","install","info")

import aiohttp
async def search(query):
    # call some HTTP‐API for your “App Store”
    async with aiohttp.ClientSession() as s:
        j = await (await s.get(f"https://repo.example.com/api?search={query}")).json()
    return [f"{pkg['id']}: {pkg['desc']}" for pkg in j["results"]]

def install(pkgid):
    # download & unpack, or shell out to `curl | sh`
    return run_cmd(["bash","-c",f"curl -fsSL https://repo.example.com/install/{pkgid} | bash"])

