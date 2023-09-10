import asyncio
import copy
import os
from glob import glob
from json import JSONDecodeError
from os.path import basename
from lxml.etree import Element, SubElement, ElementTree

import urllib.parse
import httpx
import coloredlogs
import logging

logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO')


async def fetch(name: str, filepath: str) -> dict:
    quote = urllib.parse.quote(name, safe='')
    url = f'https://api.gamer.com.tw/mobile_app/anime/v1/search.php?kw={quote}'
    detail_url = 'https://api.gamer.com.tw/mobile_app/anime/v4/video.php?acg_sn={acg_sn}&animeSn={sn_id}'
    # episode_url = 'https://api.gamer.com.tw/mobile_app/anime/v2/video.php?sn={sn_id}'
    async with httpx.AsyncClient() as client:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                 'AppleWebKit/537.36 (KHTML, like Gecko) '
                                 'Chrome/89.0.4389.114 Safari/537.36'}
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            logger.error(f'找不到資訊 - {name}')
            return {}
        result = r.json()
        # 第一個最匹配結果。
        sn_id: str = ''
        acg_sn: str = ''
        try:
            sn_id = result['anime'][0]['anime_sn']
            acg_sn = result['anime'][0]['acg_sn']
        except (JSONDecodeError, KeyError):
            logger.error(f'找不到資訊 - {name}')
            return {}
        except IndexError:
            logger.error(f'找不到資訊，沒有找到資料 - {name}')
            logger.error(result)
            return {}
        r = await client.get(detail_url.format(acg_sn=acg_sn, sn_id=sn_id), headers=headers)
        if r.status_code != 200:
            logger.error(f'找不到資訊 - {name}')
            return {}
        result = r.json()
        data: dict = {'thumb': result['data']['anime']['cover'],
                      'plot': result['data']['anime']['content'],
                      'premiered': result['data']['anime']['seasonStart'].replace('/', '-'),
                      'year': result['data']['anime']['seasonStart'].split('/')[0],
                      'root_name': 'tvshow' if result['data']['video']['type'] == 0 else 'movie',
                      'sn_id': result['data']['video']['videoSn']}
        r = await client.get(result['data']['anime']['cover'])
        filename = os.path.join(filepath, 'poster.jpg')
        with open(filename, 'wb') as f:
            f.write(r.content)
        return data


async def generate_nfo(title: str, data: dict, filepath: str):
    root_name = copy.deepcopy(data['root_name'])
    nfo_root = Element(root_name)
    data.pop('root_name')

    data['title'] = title
    for field_name, values in data.items():
        if not values:
            continue
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if field_name == 'thumb':
                output = SubElement(nfo_root, field_name, aspect='poster').text = f'{value}'
            else:
                output = SubElement(nfo_root, field_name).text = f'{value}'


    filename = os.path.join(filepath, f'{root_name}.nfo')
    ElementTree(nfo_root).write(
        filename, encoding='utf-8', xml_declaration=True, pretty_print=True, standalone=True
    )


async def main(target: str):
    alldir = glob(f'{target}/*')
    # print(alldir[0])
    logger.info(f'找到 {len(alldir)} 個動畫')
    for x in alldir:
        title = os.path.split(x)[-1]

        result = await fetch(title, x)
        if result:
            await generate_nfo(title, result, x)
        else:
            # logger.info(f'')
            logger.error(f'跳過 - {title}, {x}')
            continue


if __name__ == '__main__':
    asyncio.run(main('/sudonas/動畫瘋'))