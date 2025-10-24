from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets, permissions
from .models import Marker
from .serializers import MarkerSerializer

class MarkerView (viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    def list (self, request):
        markers = Marker.objects.all()
        serializer = MarkerSerializer(markers, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = MarkerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            marker = Marker.objects.get(pk=pk)
            marker.delete()
            return Response({'message': 'Marker deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Marker.DoesNotExist:
            return Response({'error': 'Marker not found'}, status=status.HTTP_404_NOT_FOUND)