import unittest
from pdf_print_check import parse_images

class ImageNumberTests(unittest.TestCase):
    def test_non_finite_and_invalid_image_metadata_is_rejected(self):
        for field, value in ((12, 'nan'), (13, 'inf'), (12, '-1'), (3, '0'), (4, '-2'), (0, '0'), (1, '-1')):
            fields = '1 0 image 100 100 rgb 3 8 jpeg no 1 0 300 300 1K 1%'.split()
            fields[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'Unrecognized'):
                parse_images(' '.join(fields))
        fields = '1 0 image 1 1 rgb 3 8 jpeg no 1 0 0 0 1K 1%'
        self.assertTrue(parse_images(fields)[0]['below_150_ppi'])
