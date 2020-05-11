HEADER =  {"User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.3"}
RGX = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
BLACKLIST = {
                "EXTENSIONS": ["jpeg", "jpg", "gif", "pdf", "png", "ppsx", "f4v", "mp3", "mp4", "exe", "dmg", "zip", "avi", "wmv", "pptx", "exar1", "edx", "epub"],
                "URLS": ["whatsapp", "github", "bing", "facebook", "twitter", "flicker", "youtu", "google", "flickr", "commailto", "pinterest", "linkedin", "zencart", "wufoo", "youcanbook", "instagram"],
            }
QUEUE = 100
TIMEOUT_CONSTANT = 40e3
VERSION = 0.3
LOG_DIRECTORY = "bluepugs/engine"

LOG_LEVEL = "INFO"
