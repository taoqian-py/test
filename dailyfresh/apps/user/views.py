from django.shortcuts import render,redirect
from django.views.generic import View
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.contrib.auth import authenticate,login
from celery_tasks.tasks import send_register_active_email
from user.models import User
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


    def post(self,request):
        """登陆页面"""
        # 获取数据登陆
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username,password]):
            return render(request,'login.html',{'errmsg':'数据不完整，请输入用户名和密码'})

        # 业务处理
        user = authenticate(username=username,password=password)
        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 用户被激活
                # 记录用户的登录状态
                login(request,user)
                # 要跳转到首页
                response = redirect(reverse("goods:index"))
                # 判断是否要记住用户名
                remember = request.POST.get('remember')
                if remember is 'on':
                    #要记住用户名
                    response.set_cookie("username",username,max_age=7*24*3600)
                else:
                    #不记住用户名
                    response.delete_cookie("username",username)
                return response
            else:
                # 账户没被激活
                return render(request,"login.html",{"errmsg":'账户没被激活'})
        else:
            return render(request,"login.html",{"errmsg":'用户名和密码错误'})





