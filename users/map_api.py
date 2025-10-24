from rest_framework.response import Response
from rest_framework import viewsets, permissions
from .models import Marker
from .serializers import MarkerSerializer
from .permissions import IsSilverUser, IsGoldenUser, IsArchitectUser

class MarkerView (viewsets.ViewSet):

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, IsSilverUser |
                                  IsGoldenUser | IsArchitectUser]
        elif self.action == 'destroy':
            permission_classes = [permissions.IsAuthenticated, IsGoldenUser | IsArchitectUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def list (self, request):
        markers = Marker.objects.all()
        serializer = MarkerSerializer(markers, many=True)
        return Response(serializer.data, status=200)

    def create(self, request):
        serializer = MarkerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    def destroy(self, request, pk=None):
        try:
            marker = Marker.objects.get(pk=pk)
            marker.delete()
            return Response({'message': 'Marker deleted successfully'}, status=204)
        except Marker.DoesNotExist:
            return Response({'error': 'Marker not found'}, status=404)