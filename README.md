# Blue Pugs (beta) v0.3


$$$$$$$$  $$$$   $$$$  $$$$   $$$$$$     $$$$$$$  $$$$  $$$$    $$$$$$    $$$$$
$$$$$$$$$ $$$$   $$$$  $$$$  $$$$$$$$    $$$$$$$$ $$$$  $$$$  $$$$$$$$$  $$$$$$$
$$$$ $$$$ $$$$   $$$$  $$$$ $$$$  $$$$   $$$$ $$$ $$$$  $$$$ $$$$       $$$$
$$$$$$$$  $$$$   $$$$  $$$$ $$$$$$$$$$   $$$$$$$$ $$$$  $$$$ $$$$ $$$$$$ $$$$$$$
$$$$ $$$$ $$$$   $$$$  $$$$ $$$$         $$$$$$$  $$$$  $$$$ $$$$  $$$$$     $$$$  $$
$$$$$$$$$ $$$$$$$ $$$$$$$$   $$$$        $$$       $$$$$$$$  $$$$$$$$$$  $$$$$$$  $$$$
$$$$$$$$  $$$$$$$  $$$$$$     $$$$$$     $$$        $$$$$$     $$$$$$$    $$$$$    $$


## Description

This small utility script was made to crawl websites for email addresses. It uses **multiprocessing** threads to get multiple workers to scrape the web pages, extract emails and links, and dumps them in a *.csv file.

It is quite easy to use but is in early development stage. I don't know if it will be maintained. This will depend on whether it is a useful script or not.  The code may be considered as ugly, but it works (at least for me). So if you can make it better, go ahead.

## Installation

#### Prerequisite

Everything you need to install is in the `requirements.txt` file. However, some noteworthy libraries are listed below

```
beautifulsoup4
lxml
pandas
pyzmq
```

You just need to download the repository, and install the requirements.

```sh
git clone hhttps://github.com/guanicoe/Blue-pugs-engine
python3 -m pip install -r requirements.txt
chmod +x bluePugs.py
```

## Usage

There is only one required flag `-u` which sets the target url.

#### Defaults

- **WORKERS**: By default, the number of worker is set to **40**, modify this `-w` depending on you CPU power (more is not always better).
- **LIMIT**: By default, there is a set of **5000** page limit to scan. This is a lot! But if the website has fewer accessible page, it will scan all. You can nevertheless specify no limits `-ul`.
- **DOMAIN**: By default, if **no** domain are specified, the script will just crawl and may go outside the website (* there is an exclusion list hard coded) . You can specify `-d` one or more domains to stick with.
- **OUTPUT DIRECTORY**: Two files are output. One with unique emails and a second with two columns: email, URL (with duplicates). The latter enables you to see where the email was found.




```sh
usage: bluePugs.py [-h] -u URL -d DOMAIN [DOMAIN ...] [-w WORKERS] [-l LIMIT] [-o OUTPUT_DIR] [--version]

This small utility script was made to crawl websites for email addresses. It uses multiprocessing threads to get multiple workers to scrape the web pages,
extract emails and links, and dumps them in a *.csv file.

optional arguments:
  -h, --help            show this help message and exit
  -u URL, --url URL     Url to crawl
  -d DOMAIN [DOMAIN ...], --domain DOMAIN [DOMAIN ...]
                        Domain name to keep in scope (ex: -d domain1, domain2). The first domain will be used as name for output.
  -w WORKERS, --workers WORKERS
                        Number of workers (default: 10)
  -l LIMIT, --limit LIMIT
                        Limite the number of pages to crawl (default: 1000)
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Specify which directory to save the date. (default is URL)
  --version             Returns the version number

```

## TO-DO

- finish README :)





G
