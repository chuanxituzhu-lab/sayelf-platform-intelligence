"""Curated public official-document endpoints, not a claim of verified rules."""
from .contracts import Source

# id, kind, title, URL, expected visible body markers. Independent product scopes.
CATALOG = {
 'YouTube': [
  ('youtube-policy','POLICY','社区准则','https://support.google.com/youtube/answer/9288567?hl=en',('Community Guidelines',)),
  ('youtube-algorithm','ALGORITHM','推荐与表现官方说明','https://support.google.com/youtube/answer/141805?hl=en',('recommendations','recommended')),
  ('youtube-api','API','YouTube Data API 文档','https://developers.google.com/youtube/v3/docs',('YouTube Data API',)),
  ('youtube-product','PRODUCT','YouTube 官方产品公告','https://blog.youtube/news-and-events/',('YouTube',)),
 ],
 'Instagram': [
  ('instagram-policy','POLICY','Meta 社区守则（需核对Instagram适用范围）','https://transparency.meta.com/policies/community-standards/',('Community Standards',)),
  ('instagram-algorithm','ALGORITHM','Explore 推荐系统工程说明（历史文档）','https://engineering.fb.com/2023/08/09/ml-applications/scaling-instagram-explore-recommendations-system/',('Instagram Explore',)),
  ('instagram-api','API','Instagram 平台文档','https://developers.facebook.com/docs/instagram-platform/',('Instagram',)),
 ],
 'Facebook': [
  ('facebook-policy','POLICY','Facebook 社区守则','https://transparency.meta.com/policies/community-standards/',('Community Standards',)),
  ('facebook-algorithm','ALGORITHM','Facebook与Instagram排序官方说明（历史文档）','https://about.fb.com/news/2023/06/how-ai-ranks-content-on-facebook-and-instagram/',('Facebook','Instagram')),
  ('facebook-api','API','Graph API 文档','https://developers.facebook.com/docs/graph-api/',('Graph API',)),
 ],
 'Reddit': [
  ('reddit-policy','POLICY','Reddit 规则','https://redditinc.com/policies/reddit-rules',('Reddit Rules',)),
  ('reddit-api','API','Reddit 开发者条款','https://redditinc.com/policies/developer-terms',('Developer Terms',)),
  ('reddit-product','PRODUCT','Reddit 官方公告','https://redditinc.com/news',('Reddit',)),
 ],
 'TikTok': [
  ('tiktok-policy','POLICY','TikTok 社区准则','https://www.tiktok.com/community-guidelines/en/',('Community Guidelines',)),
  ('tiktok-algorithm','ALGORITHM','推荐内容官方帮助','https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content',('recommends content',)),
  ('tiktok-api','API','TikTok 开发者文档','https://developers.tiktok.com/docs/en/welcome',('TikTok',)),
 ],
 '小红书': [
  ('xiaohongshu-policy','POLICY','小红书社区公约（官方蒲公英帮助页）','https://pgy.xiaohongshu.com/help/detail?id=1eda0a065dd894063c2e029a49e8f6a1&userType=4',('社区公约','社区行为规范')),
  ('xiaohongshu-api','API','小红书开放平台文档（限开放平台业务）','https://open.xiaohongshu.com/document',('小红书',)),
  ('xiaohongshu-product','PRODUCT','小红书创作服务官方入口','https://creator.xiaohongshu.com/',('创作','小红书')),
 ],
 '抖音': [
  ('douyin-policy','POLICY','抖音用户服务协议','https://www.douyin.com/draft/douyin_agreement/douyin_agreement_user.html',('用户服务协议',)),
  ('douyin-api','API','抖音开放平台开发者协议','https://open.douyin.com/platform/resource/docs/operation-standard/agreement-protocol',('开发者','开放平台')),
  ('douyin-product','PRODUCT','抖音安全与信任中心公告','https://trust.douyin.com/',('安全与信任','抖音')),
 ],
 '视频号': [
  ('channels-policy','POLICY','微信视频号运营规范官方入口（正文需核对）','https://weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_agreement&s=video',('视频号',)),
  ('channels-product','PRODUCT','视频号助手官方入口（可能需登录）','https://channels.weixin.qq.com/',('视频号',)),
 ],
 '公众号': [
  ('offiaccount-policy','POLICY','微信公众平台运营规范官方入口','https://mp.weixin.qq.com/cgi-bin/readtemplate?t=business/faq_operation_tmpl&type=info&lang=zh_CN',('运营规范',)),
  ('offiaccount-api','API','微信公众号接入文档','https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Access_Overview.html',('公众号','公众平台')),
 ],
 '哔哩哔哩': [
  ('bilibili-policy','POLICY','哔哩哔哩社区公约','https://member.bilibili.com/studio/convention/',('社区公约',)),
  ('bilibili-api','API','哔哩哔哩开放平台管理规范','https://openhome.bilibili.com/agreement/management-protocol',('开发者','管理规范')),
 ],
}

# Observed official redirects, explicitly scoped; never allow an entire shared host.
REDIRECTS = {
 'Instagram': ('https://developers.facebook.com/documentation/instagram-platform',),
 'TikTok': ('https://www.tiktok.com/safety/en/policies-and-engagement/overview',
            'https://www.tiktok.com/support/faq_detail?id=7655285288050104852'),
 '公众号': ('https://developers.weixin.qq.com/doc/service/guide/dev/',),
}

def sources_for(platform):
 return [Source(i,platform,kind,url,title,ttl_hours=168 if kind in ('POLICY','API') else 720)
         for i,kind,title,url,markers in CATALOG[platform]]

def markers_for(source):
 return next((row[4] for row in CATALOG.get(source.platform,[]) if row[0]==source.id),())

def hosts_for(platform):
 from urllib.parse import urlsplit
 return {urlsplit(row[3]).hostname for row in CATALOG.get(platform,[])}
