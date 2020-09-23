from django.shortcuts import render,redirect
from django.views.generic import View
from django.core.cache import cache
from django.core.urlresolvers import reverse
from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from order.models import OrderGoods
from django_redis import get_redis_connection
from django.core.paginator import Paginator
# Create your views here.


class IndexView(View):
    """首页展示"""
    def get(self,request):
        """显示首页"""
        # 尝试从缓存中获取数据
        context = cache.get('index_page_data')
        if context is None:
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

                # 组织前端模版上下文
                content = {"types": types, "goods_banner": goods_banners,
                           "promotion_banners": promotion_banners}

                cache.set('index_page_data',content,3600)

        # 获取购物车的信息
        # 获取用户
        user = request.user
        cart_count = 0

        if user.is_authenticated():
            # 用户已经登陆
            conn = get_redis_connection('default')
            cart_key = "cart_%d"%user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context.update(cart_count=cart_count)

        return render(request,'index.html',context)


class DetailView(View):
    """详情页"""
    def get(self,request,goods_id):
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse("goods:index"))
        # 获取商品的分类信息
        types = GoodsType.objects.all()

        # 获取商品的评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by("-create_time")[:2]

        # 获取同一个SPU的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0

        if user.is_authenticated():
            #判断用户是否已经登陆
            conn = get_redis_connection('default')
            cart_key = "cart_%d"%user.id
            cart_count = conn.hlen(cart_key)

            #添加用户的历史浏览记录
            conn = get_redis_connection('default')
            history_key = "history_%d"%user.id
            # 移除列表中的goods_id
            conn.lrem(history_key,0,goods_id)
            # 把goods_id插入到列表的左侧
            conn.lpush(history_key,goods_id)
            # 只保存用户最新浏览的5条信息
            conn.ltrim(history_key,0,4)

        # 组织上下文模板
        context = {'sku':sku, 'types':types,
                   'sku_orders':sku_orders,
                   'new_skus':new_skus,
                   'same_spu_skus':same_spu_skus,
                   'cart_count':cart_count}

        return render(request,'detail.html',context)


class ListView(View):
    """列表页"""
    def get(self,request,type_id,page):
        '''显示列表页'''
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse("goods:index"))

        # 获取商品的分类信息
        types = GoodsType.objects.all()

        sort = request.GET.get('sort')

        # 按照选项进行排序
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by("price")
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by("-sales")
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')


        # 获取分页对象
        paginator = Paginator(skus,1)

        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        skus_page = paginator.page(page)

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by("-create_time")[:2]

        # 获取购物车商品的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context = {'type':type, 'types':types,
                   'skus_page':skus_page,
                   'new_skus':new_skus,
                   'cart_count':cart_count,
                   'sort':sort}

        return render(request,'list.html',context)


