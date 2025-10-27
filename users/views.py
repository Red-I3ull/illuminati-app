from django.shortcuts import render
from rest_framework import viewsets, permissions
from .serializers import LoginSerializer, RegisterSerializer, EntryPasswordSerializer
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from knox.models import AuthToken
from .models import EntryPassword
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()


@method_decorator(csrf_exempt, name='dispatch')
class VerifyEntryPasswordViewset(viewsets.ViewSet):
    """Viewset for verifying entry password."""
    permission_classes = [permissions.AllowAny]
    serializer_class = EntryPasswordSerializer

    def create(self, request):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            password = serializer.validated_data['password']

            try:
                entry_password = EntryPassword.objects.filter(is_active=True).first()

                if not entry_password:
                    return Response(
                        {'error': 'Entry password not configured'},
                        status=500
                    )

                if entry_password.password == password:
                    return Response(
                        {
                            'success': True,
                            'message': 'Entry password verified successfully'
                        },
                        status=200
                    )
                else:
                    return Response(
                        {
                            'success': False,
                            'error': 'Incorrect password'
                        },
                        status=401
                    )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=500
                )
        else:
            return Response(serializer.errors, status=400)


class LoginViewset(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def create(self, request): 
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(): 
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(request, username=username, password=password)
            if user: 
                _, token = AuthToken.objects.create(user)
                return Response(
                    {
                        "user": self.serializer_class(user).data,
                        "token": token
                    }
                )
            else: 
                return Response({"error":"Invalid credentials"}, status=401)    
        else: 
            return Response(serializer.errors,status=400)



class RegisterViewset(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def create(self,request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else: 
            return Response(serializer.errors,status=400)