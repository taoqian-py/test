from django.shortcuts import render,redirect
from django.views.generic import View
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.contrib.auth import authenticate,login,logout
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from celery_tasks.tasks import send_register_active_email
from user.models import User,Address
from goods.models import GoodsSKU
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
import re
# Create your views here.


class RegisterView(View):

    def get(self,request):
        return render(request,'register.html')


    def post(self,request):

        # 获取数据
        username = request.POST.get("user_name")
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据校验
        if not all([username,password,email]):
            return render(request,'register.html',{'errmsg':'数据不完整'})

        # 校验邮箱
        if not re.match(r"^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$",email):
            return render(request,'register.html',{'errmsg':'邮箱格式不正确'})
        # 判断是否同意协议
        if allow != 'on':
            return render(request,'register.html',{'errmsg':'请同意协议'})
        # 查询数据库看是否存在用户名
        try:
            user = User.objects.get(username=username)
        # 查不到用户名为空
        except User.DoesNotExist:
            user = None
        # 如果有用户名，直接返回注册页面
        if user:
            return render(request,'register.html',{'errmsg':'用户名已存在'})

        # 业务处理，添加用户到数据库，并设置为为激活状态
        user = User.objects.create_user(username,email,password)
        user.is_active = 0
        user.save()

        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY,3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info)
        token = token.decode('utf-8')


        # 使用celery进行异步发送邮件
        send_register_active_email.delay(email,username,token)

        return redirect(reverse('goods:index'))


class ActiveView(View):

    def get(self,request,token):
        # 揭秘用户的身份信息
        serializer = Serializer(settings.SECRET_KEY,3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']

            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('goods:login'))
        # 解密不成功说明连接已失效
        except SignatureExpired as e:
            return HttpResponse("激活连接已失效")


class LoginView(View):

    def get(self,request):
        """显示登陆页面"""

        # 判断cookie中是否有用户名
        if "username" in request.COOKIES:
            username = request.COOKIES.get("username")
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request,'login.html',{"username":username,"checked":checked})

    def post(self, request):
        '''登录校验'''
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})

        # 业务处理:登录校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request, user)

                # 获取登录后所要跳转到的地址
                # 默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))

                # 跳转到next_url
                response = redirect(next_url) # HttpResponseRedirect

                # 判断是否需要记住用户名
                remember = request.POST.get('remember')

                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')

                # 返回response
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})




class LogoutView(View):
    def get(self,request):
        # 退出登陆，清除登陆session信息
        logout(request)
        return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiredMixin, View):
    """用户中心信息页面"""
    def get(self,request):
        # 显示
        # 获取个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 利用缓存使用到了redis
        conn = get_redis_connection('default')

        # 获取用户的历史浏览记录
        history_key = "history_%d"%user.id

        # 获取浏览过的sku——id
        sku_ids = conn.lrange(history_key,0,4)

        goods_list = []
        # 从数据库中读取sku商品
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_list.append(goods)

        # 组织前端模板数据
        content = {
            "page":"info",
            "address":address,
            "goods_list":goods_list
        }

        return render(request,'user_center_info.html',content)


class UserOrderView(LoginRequiredMixin, View):
    """用户中心订单页面"""
    def get(self,request):

        return render(request,'user_center_order.html',{"page":"order"})


class AddressView(LoginRequiredMixin, View):

    """用户中心地址页面"""
    def get(self,request):
        # 获取用户的信息
        user = request.user
        # 获取用户默认的收货地址
        address = Address.objects.get_default_address(user)
        # 组织上下文
        content = {"page":"address","address":address}

        return render(request,'user_center_site.html',content)


    def post(self,request):
        '''地址的添加'''
        # 接收数据
        reciver = request.POST.get("reciver")
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        phone = request.POST.get("phone")

        # 校验数据完整性
        if not all([reciver,addr,phone]):
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})

        # 校验手机号
        if not re.match(r"1[3578]{9}",phone):
            return render(request, 'user_center_site.html', {'errmsg':'手机格式不正确'})

        # 业务处理-添加默认地址
        # 获取用户对象
        user = request.user
        address = Address.objects.get_default_address(user)

        # 如果已经存在默认收货地址
        if address:
            is_default = True
        else:
            is_default= False

        Address.objects.create(user=user,
                               reciver=reciver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        return redirect(reverse("user:address"))