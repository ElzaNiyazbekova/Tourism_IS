"""stored_files: uploaded files kept inside the database.   Owner: Aitore

Used on hosting where the disk is wiped on every restart (Render free tier): set MEDIA_STORAGE=db and every
FileField (tour photos) is written here instead of MEDIA_ROOT. Local runs keep using the normal disk storage.
"""
from django.db import models


class StoredFile(models.Model):
    id = models.AutoField(primary_key=True, db_column="file_id")
    name = models.CharField(max_length=200, unique=True)      # same value the FileField stores, e.g. tour_photos/ab12.jpg
    content = models.BinaryField()
    size = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stored_files"
        constraints = [models.CheckConstraint(condition=models.Q(size__gte=0), name="ck_stored_files_size")]

    def __str__(self):
        return self.name
