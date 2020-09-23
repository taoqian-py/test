from django.shortcuts import render
from django.views.generic import View
from goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from django_redis import get_redis_connection
# Create your views here.


class IndexView(View):
    """首页展示"""
    def get(self,request):
        """显示首页"""
        # 获取首页展示的信息
        types = GoodsType.objects.all()

        # 获取首页轮播图的信息
        goods_banners = IndexGoodsBanner.objects.all().order_by('index')

        # 获取首页活动的信息
        promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

        # 获取首页分类展示信息
        for type in types:
            # 获取商品分类展示的图片bannaer
            image_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=1).order_by('index')
            # 获取商品分类展示的标题banner
            title_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=0).order_by('index')

            # 动态的给type增加属性
            type.image_banners = image_banners
            type.title_banners = title_banners

        # 获取购物车的信息
        # 获取用户
        user = request.user
        cart_count = 0

        if user.is_authenticated():
            # 用户已经登陆
            conn = get_redis_connection('default')
            cart_key = "cart_%d"%user.id
            cart_count = conn.hlen(cart_key)

        # 组织前端模版上下文
        content = {"types":types,"goods_banner":goods_banners,
                   "promotion_banners":promotion_banners,"cart_count":cart_count}

        return render(request,'index.html',content)



