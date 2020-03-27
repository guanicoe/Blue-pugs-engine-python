# Crawler 

version: 0.2





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
git clone https://github.com/guenicoe/crawler
python3 -m pip install -r requirements.txt
chmod +x crawler.py
```

## Usage

