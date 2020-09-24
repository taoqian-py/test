from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse

from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
# Create your views here.


class CartAddView(View):

    def post(self,request):
        """购物车添加"""
        user = request.user
        if not user.is_authenticated():
            #用户没有进行登陆
            return JsonResponse({'res':0,'errmsg':'您还没进行登陆'})

        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验数据
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})


        # 尝试添加商品
        try:
            count = int(count)
        except Exception as e:
            # 数目有问题
            return JsonResponse({'res':2,'errmsg':'添加的数目有问题，请重新输入'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':3,'errmsg':'您查询的商品不存在'})

        # 业务处理，添加购物车
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        cart_count = conn.hlen(cart_key)

        if cart_count:
            # 累加购物车中商品的数目
            count += cart_count

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res':4,'errmsg':'商品库存不足'})

        # 设置购物车中sku_id对应的值
        conn.hset(cart_key,sku_id,count)

        # 计算用户购物车商品的条目数
        total_count = conn.hlen(cart_key)

        # 返回
        return JsonResponse({'res':5,'total_count':total_count,'message':'添加成功'})


class CartInfoView(LoginRequiredMixin,View):
    """购物车页面展示"""
    def get(self,request):
        # 获取用户
        user = request.user
        # 获取购物车商品的信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # 获取商品的id
        cart_dict = conn.hgetall(cart_key)

        skus = []
        # 保存用户购物车中商品的总数目和总价格
        total_count = 0
        total_price = 0
        # 遍历获取商品的信息
        for sku_id,count in cart_dict.items():
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            # 动态给sku对象增加一个属性amount, 保存商品的小计
            sku.amount = amount
            # 动态给sku对象增加一个属性count, 保存购物车中对应商品的数量
            sku.count = count
            # 添加
            skus.append(sku)
            # 累加计算商品的总数目和总价格
            total_count += int(count)
            total_price += amount

        # 组织上下文
        context = {'total_count':total_count,
                   'total_price':total_price,
                   'skus':skus}

        return render(request,'cart.html',context)


# /cart/update
class CartUpdateView(View):
    '''购物车记录更新'''
    def post(self,request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'请您先进性登陆'})

        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})
        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理:更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

        # 更新
        conn.hset(cart_key,sku_id,count)

        # 计算用户购物车中商品的总件数 {'1':5, '2':3}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({"res":5,"total_count":total_count, 'message':'更新成功'})

# /cart/delete
class CartDeleteView(View):
    """删除购物车"""
    def post(self,request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})

        sku_id = request.POST.get('sku_id')

        # 数据校验
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '获取不到商品'})


        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 业务处理
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        conn.hdel(cart_key,sku_id)

        # 计算用户购物车中商品的总件数 {'1':5, '2':3}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res':3,'message':'更新成功','total_count':total_count})












