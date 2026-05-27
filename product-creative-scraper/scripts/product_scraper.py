#!/usr/bin/env python3
"""
商品信息提取器
支持电商产品、App Store、Google Play
"""

import json
import re
import sys
from urllib.parse import urljoin, urlparse


def ensure_https(url):
    """确保URL使用HTTPS协议"""
    if url and isinstance(url, str):
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('http://'):
            return url.replace('http://', 'https://', 1)
        return url
    return url

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Optional scraper dependencies missing. Install with: pip install requests beautifulsoup4")


# ==================== URL类型识别 ====================

def detect_url_type(url):
    """
    识别URL类型

    Returns:
        'appstore' - App Store
        'googleplay' - Google Play
        'ecommerce' - 电商独立站
        'unknown' - 未知类型
    """
    domain = urlparse(url).netloc.lower()

    # App Store
    if 'apps.apple.com' in domain:
        return 'appstore'

    # Google Play
    if 'play.google.com' in domain:
        return 'googleplay'

    # 电商独立站（包含products关键字或已知电商域名）
    if '/products/' in url or '/p/' in url:
        # 检查是否是已知电商域名
        ecommerce_patterns = [
            'shopify', 'shop', 'store', 'myshopify',
            'amazon', 'ebay', 'aliexpress', 'etsy', 'walmart',
            'shoplaza', 'bigcartel', 'squarespace', 'woocommerce'
        ]
        if any(pattern in domain for pattern in ecommerce_patterns):
            return 'ecommerce'
        # 如果URL包含/products/路径，也视为电商
        if '/products/' in url:
            return 'ecommerce'

    return 'ecommerce'  # 默认按电商处理


# ==================== App Store 解析 ====================

def scrape_appstore(url):
    """解析 App Store 应用信息"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text

        # 获取应用名称 - 从多种模式中提取
        name = None
        name_patterns = [
            r'<h1[^>]*class="product-header__title[^"]*"[^>]*>([^<]+)</h1>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<title>(.+?)\s+(?:on the )?App Store',
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, html_content)
            if match:
                name = match.group(1).strip()
                # 清理常见的多余文字
                name = re.sub(r'\s+(?:on the )?App Store$', '', name, flags=re.IGNORECASE)
                if 2 < len(name) < 200:
                    break

        # 获取应用图片（图标 + 截图）
        images = []

        # 应用图标 - 优先从meta标签
        icon_patterns = [
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'<link[^>]*rel=["\']apple-touch-icon["\'][^>]*href=["\']([^"\']+)["\']',
        ]
        for pattern in icon_patterns:
            match = re.search(pattern, html_content)
            if match:
                icon_url = match.group(1)
                if not icon_url.startswith('http'):
                    icon_url = 'https:' + icon_url if icon_url.startswith('//') else urljoin(url, icon_url)
                icon_url = ensure_https(icon_url)
                images.append(icon_url)
                break

        # 应用截图 - 查找 PurpleSource 路径的截图
        # 匹配 srcset 中的URL格式: .../filename.png/xxxxyybb.webp
        screenshot_urls = re.findall(
            r'(https://is[\d\-]*ssl\.mzstatic\.com/image/thumb/PurpleSource[^"]+?/\d+x\d+bb\.[a-z]+)',
            html_content
        )

        # 去重并过滤掉图标
        seen_base = set()
        for img_url in screenshot_urls:
            # 跳过图标
            if 'AppIcon' in img_url or 'app-icon' in img_url.lower():
                continue

            # 提取文件标识用于去重（路径中的唯一标识）
            # PurpleSource211/v4/5b/00/ba/5b00bac0-f389-c159-488f-f18c92d014ef/_U4e0a_U67b6_01
            base_match = re.search(r'PurpleSource[^/]+/v\d+/[^/]+/[^/]+/([^/]+/[^/]+)', img_url)
            if base_match:
                base_id = base_match.group(1)
                if base_id not in seen_base:
                    seen_base.add(base_id)
                    # 使用较大的尺寸
                    clean_url = re.sub(r'/\d+x\d+bb\.', '/600x1300bb.', img_url)
                    images.append(clean_url)
                    if len(images) >= 3:
                        break

        # 确保最多3张图片
        images = images[:3]

        if name:
            return {'name': name, 'images': images}

        return {'error': '无法提取App应用信息'}

    except Exception as e:
        return {'error': f'App Store解析失败: {str(e)}'}


# ==================== Google Play 解析 ====================

def scrape_googleplay(url):
    """解析 Google Play 应用信息"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text

        # 获取应用名称 - 从meta标签获取最准确
        name = None
        # 优先从 og:title 获取，然后清理
        og_title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html_content)
        if og_title_match:
            name = og_title_match.group(1).strip()
            # 清理 " - Apps on Google Play" 等后缀
            name = re.sub(r'\s+-\s+Apps\s+(?:on\s+)?Google Play.*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s+-\s+.*$', '', name)  # 移除任何 - 后的内容

        # 如果没有找到，尝试其他模式
        if not name or len(name) < 2:
            fallback_patterns = [
                r'<h1[^>]*itemprop=["\']name["\'][^>]*>([^<]+)</h1>',
                r'<title>([^<]+?)\s*(?:?:-|\s+Apps\s+(?:on\s+)?Google Play)',
            ]
            for pattern in fallback_patterns:
                match = re.search(pattern, html_content)
                if match:
                    name = match.group(1).strip()
                    if len(name) > 2:
                        break

        # 获取应用图片
        images = []

        # 应用图标 - 从meta标签获取
        og_image_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html_content)
        icon_base = None
        if og_image_match:
            icon_url = og_image_match.group(1)
            # 移除尺寸参数以获取原图
            icon_base = re.sub(r'=w\d+-h\d+.*', '', icon_url)
            if not icon_base.startswith('http'):
                icon_base = 'https:' + icon_base if icon_base.startswith('//') else urljoin(url, icon_base)
            icon_base = ensure_https(icon_base)

        # 查找所有 play-lh URL
        all_urls = re.findall(
            r'(https://play-lh\.googleusercontent\.com/[a-zA-Z0-9\-._~:/?#[\]@!$&()*+,;=%]+)[,\"\s\']',
            html_content
        )

        # 去重并收集图片
        seen = set()
        promo_images = []  # 宣传图/横幅
        screenshots = []   # 截图

        for img_url in all_urls:
            img_url = img_url.strip('"\'')

            # 基础URL用于去重（去掉参数）
            base = re.sub(r'=.*', '', img_url)

            if base in seen:
                continue

            # 跳过图标
            if icon_base and base == icon_base:
                continue

            seen.add(base)

            # 检查尺寸参数
            size_match = re.search(r'=w(\d+)-h(\d+)', img_url)
            if not size_match:
                continue

            w, h = int(size_match.group(1)), int(size_match.group(2))
            ratio = h / w if w > 0 else 0

            # 根据尺寸和宽高比分类
            # Banner/promo: ratio ~0.5-0.6 (横幅)
            # Screenshot: ratio > 1.5 (竖屏截图) or ratio < 0.7 but not banner (横屏截图)
            if 0.45 <= ratio <= 0.65 and w > 300:
                promo_images.append(img_url)
            elif ratio > 1.5 and w > 200:
                screenshots.append(img_url)
            elif ratio < 0.7 and w > 300 and h > 200:
                # 可能的横屏截图
                screenshots.append(img_url)

        # 优先使用截图，如果没有则使用宣传图，最后使用图标
        if screenshots:
            images = screenshots[:3]
        elif promo_images:
            images = promo_images[:3]
        elif icon_base:
            images = [icon_base]

        # 确保所有URL使用HTTPS
        images = [ensure_https(img) for img in images]

        # 确保最多3张图片
        images = images[:3]

        if name:
            return {'name': name, 'images': images}

        return {'error': '无法提取Android应用信息'}

    except Exception as e:
        return {'error': f'Google Play解析失败: {str(e)}'}


# ==================== 电商产品解析 ====================

def extract_from_json_ld(soup, base_url):
    """从 JSON-LD 结构化数据中提取商品信息"""
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            # 处理单个产品或包含@graph的情况
            if isinstance(data, list):
                for item in data:
                    result = _parse_product_data(item, base_url)
                    if result:
                        return result
            elif isinstance(data, dict):
                if '@graph' in data:
                    for item in data['@graph']:
                        result = _parse_product_data(item, base_url)
                        if result:
                            return result
                result = _parse_product_data(data, base_url)
                if result:
                    return result
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return None


def _parse_product_data(item, base_url):
    """解析单个产品数据"""
    if item.get('@type') != 'Product':
        return None

    name = item.get('name')
    if not name:
        return None

    # 获取价格
    price = None
    offers = item.get('offers', {})
    if isinstance(offers, dict):
        price = offers.get('price')
    elif isinstance(offers, list) and offers:
        price = offers[0].get('price')

    # 获取最多3张图片
    images = []
    if 'image' in item:
        image_data = item['image']
        image_list = []

        import html as html_module

        if isinstance(image_data, str):
            # 先解码HTML实体
            image_data = html_module.unescape(image_data)

            # 处理逗号分隔的图片URL (Shopline格式)
            if ',' in image_data and 'http' in image_data:
                image_list = []
                parts = image_data.split(',https://')
                for i, part in enumerate(parts):
                    if i == 0:
                        url = part
                    else:
                        url = 'https://' + part
                    image_list.append(url)
            else:
                image_list = [image_data]
        elif isinstance(image_data, list):
            # 检查列表中的第一个元素是否包含逗号分隔的URL
            if image_data and isinstance(image_data[0], str):
                first_img = image_data[0]
                # 先解码HTML实体
                first_img = html_module.unescape(first_img)
                # 如果包含逗号和http，则是Shopline格式
                if ',' in first_img and 'http' in first_img:
                    image_list = []
                    parts = first_img.split(',https://')
                    for i, part in enumerate(parts):
                        if i == 0:
                            url = part
                        else:
                            url = 'https://' + part
                        image_list.append(url)
                else:
                    image_list = image_data
            else:
                image_list = image_data

        # 取前3张，转换为绝对URL并确保HTTPS
        for img in image_list[:3]:
            if img and isinstance(img, str):
                if not img.startswith('http'):
                    img = urljoin(base_url, img)
                img = ensure_https(img)
                images.append(img)

    return {
        'name': name,
        'price': price,
        'images': images
    }


def extract_from_meta(soup, base_url):
    """从 meta 标签中提取商品信息（备用方案）"""
    name = None
    price = None
    images = []

    # 商品名称
    for meta in soup.find_all('meta', property='og:title'):
        if meta.get('content'):
            name = meta['content']
            break

    # 价格 - 尝试多个可能的标签
    for prop in ['product:price:amount', 'og:price:amount']:
        for meta in soup.find_all('meta', property=prop):
            if meta.get('content'):
                price = meta['content']
                break
        if price:
            break

    # 图片 - 尝试获取多张
    for meta in soup.find_all('meta', property='og:image'):
        if meta.get('content'):
            img = meta['content']
            if not img.startswith('http'):
                img = urljoin(base_url, img)
            img = ensure_https(img)
            if img not in images:
                images.append(img)
                if len(images) >= 3:
                    break

    if name:
        return {'name': name, 'price': price, 'images': images}
    return None


def extract_from_shopify_js(html_content, base_url):
    """从 Shopify JavaScript 变量中提取商品信息"""
    images = []

    # 找到 images: 或 "images": 数组的位置
    images_start = html_content.find('images: [')
    if images_start == -1:
        images_start = html_content.find('"images": [')

    if images_start != -1:
        # 截取数组所在区域（最多10000字符，因为数组可能很长）
        array_region = html_content[images_start:images_start + 10000]

        # 查找数组结束位置
        depth = 0
        found_start = False
        array_end = 0

        for i, char in enumerate(array_region):
            if char == '[':
                depth += 1
                found_start = True
            elif char == ']':
                depth -= 1
                if found_start and depth == 0:
                    array_end = i + 1
                    break

        array_content = array_region[:array_end]

        # 简单方法：匹配所有引号包裹的字符串，然后过滤出图片URL
        quoted_strings = re.findall(r'"([^"]+)"', array_content)

        for raw_url in quoted_strings:
            # 先清理转义字符
            url = raw_url.replace('\\/', '/')

            # 筛选出包含 files/ 和图片扩展名的URL
            if '/files/' not in url:
                continue
            if not re.search(r'\.(jpg|jpeg|png|webp)', url, re.IGNORECASE):
                continue

            # 转换为完整URL并确保HTTPS
            if url.startswith('//'):
                url = 'https:' + url
            url = ensure_https(url)

            # 去重：使用基础文件名（去掉尺寸后缀和版本参数）
            filename = url.split('/')[-1]
            base_name = re.sub(r'_[0-9]+x[0-9]*', '', filename)
            base_name = re.sub(r'\?v=[0-9]+', '', base_name)
            base_name = re.sub(r'_[a-f0-9-]{20,}', '', base_name)

            # 检查是否已存在相同基础文件名的图片
            exists = False
            for existing in images:
                existing_filename = existing.split('/')[-1]
                existing_base = re.sub(r'_[0-9]+x[0-9]*', '', existing_filename)
                existing_base = re.sub(r'\?v=[0-9]+', '', existing_base)
                existing_base = re.sub(r'_[a-f0-9-]{20,}', '', existing_base)
                if base_name == existing_base:
                    exists = True
                    break

            if not exists:
                images.append(url)
                if len(images) >= 3:
                    break

    # 如果找到了图片，也尝试获取标题和价格
    if images:
        # 查找标题
        title_patterns = [
            r'<h1[^>]*>([^<]+)</h1>',
            r'"title"\s*:\s*"([^"]{10,100})"',
        ]
        name = None
        for pattern in title_patterns:
            match = re.search(pattern, html_content)
            if match:
                name = match.group(1).strip()
                if len(name) < 100:
                    name = re.sub(r'^CRZ YOGA\s+', '', name)
                    break

        # 查找价格
        price_patterns = [
            r'"price"\s*:\s*"(\d+)"',
            r'"price"\s*:\s*(\d+)',
        ]
        price = None
        for pattern in price_patterns:
            match = re.search(pattern, html_content)
            if match:
                try:
                    price_val = float(match.group(1))
                    if price_val > 100:
                        price = price_val / 100
                    else:
                        price = price_val
                    if 1 < price < 10000:
                        break
                except (ValueError, TypeError):
                    continue

        if name:
            return {'name': name, 'price': price, 'images': images}

    return None


def extract_from_html(soup, base_url):
    """直接从 HTML 中提取（最后备选方案）"""
    name = None
    price = None
    images = []

    # Shopify 常见的标题选择器
    selectors = [
        'h1.product-title',
        'h1.product__title',
        'h1.product-single__title',
        'h1[class*="product"][class*="title"]',
        'h1',
    ]

    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            name = elem.get_text(strip=True)
            break

    # 价格选择器
    price_selectors = [
        '.price__regular .money',
        '.product-single__price',
        '[class*="price"]',
    ]

    for selector in price_selectors:
        elem = soup.select_one(selector)
        if elem:
            price_text = elem.get_text(strip=True)
            price_match = re.search(r'[\$€£¥]?\s*[\d,]+\.?\d*', price_text)
            if price_match:
                price = price_match.group()
            break

    # 图片 - 获取多张产品图片
    for img in soup.select('img[class*="product"]')[:3]:
        src = img.get('src') or img.get('data-src')
        if src:
            if not src.startswith('http'):
                src = urljoin(base_url, src)
            src = ensure_https(src)
            if src not in images:
                images.append(src)

    if name:
        return {'name': name, 'price': price, 'images': images}
    return None


def scrape_ecommerce(url):
    """解析电商独立站商品信息"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')

        # 优先从Shopify JS获取图片（原图版本）
        shopify_result = extract_from_shopify_js(html_content, url)

        if shopify_result:
            result = shopify_result
        else:
            result = extract_from_json_ld(soup, url)
            if not result:
                result = extract_from_meta(soup, url)
            if not result:
                result = extract_from_html(soup, url)

        if result and 'error' not in result:
            if 'images' in result and len(result['images']) > 3:
                result['images'] = result['images'][:3]
            result['url'] = url
            return result

        return {'error': '无法提取商品信息'}

    except Exception as e:
        return {'error': str(e)}


# ==================== 主函数 ====================

def scrape_product(url):
    """
    提取商品/应用信息

    Args:
        url: 商品/应用页面URL

    Returns:
        dict:
            电商产品: {'name': str, 'price': float, 'images': list}
            App产品: {'name': str, 'images': list}
    """
    try:
        url_type = detect_url_type(url)

        if url_type == 'appstore':
            return scrape_appstore(url)
        elif url_type == 'googleplay':
            return scrape_googleplay(url)
        else:
            return scrape_ecommerce(url)

    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python product_scraper.py <URL>")
        print("支持: 电商独立站、App Store、Google Play")
        sys.exit(1)

    url = sys.argv[1]
    result = scrape_product(url)

    print(json.dumps(result, ensure_ascii=False, indent=2))
