import os
import tempfile
import unittest
from PIL import Image, ImageChops, ImageDraw

TEMP = tempfile.TemporaryDirectory(prefix='mycut-emoji-tests-')
os.environ.setdefault('MYCUT_DATA_DIR', TEMP.name)
from mycut import typeset, google_fonts, block_render, captions, flow, scene_layout

STYLE = {'text_color': '#29231F', 'background': '#FBF8F1', 'accent': '#c85e37', 'google_font': 'Roboto'}


def yellow(image):
    """Pixels of the 😳 face: saturated yellow never comes from the dark text color."""
    return sum(1 for r, g, b, *rest in image.convert('RGBA').get_flattened_data()
               if (not rest or rest[0] > 200) and r > 220 and 160 < g < 235 and b < 110)


@unittest.skipUnless(typeset.emoji_face(), 'Noto Color Emoji não instalada')
class EmojiTextTests(unittest.TestCase):
    def setUp(self):
        self.face = google_fonts.face('Roboto', 64)

    def test_emoji_sequences_stay_whole(self):
        self.assertEqual(typeset.clusters('a👨‍👩‍👧🇧🇷#️⃣👍🏽'), ['a', '👨‍👩‍👧', '🇧🇷', '#️⃣', '👍🏽'])
        self.assertEqual(typeset.runs('é só um apelido 😳', self.face), [('é só um apelido ', False), ('😳', True)])
        # Plain digits and text-presentation selectors stay in the text face.
        self.assertFalse(typeset.has_emoji('Claude Code 3.0', self.face))
        self.assertFalse(typeset.has_emoji('☺︎', self.face))

    def test_line_without_emoji_keeps_pillow_pixels(self):
        first, second = (Image.new('RGB', (700, 120), '#fff') for _ in range(2))
        ImageDraw.Draw(first).text((350, 60), 'Claude Code 3.0', font=self.face, fill='#222', anchor='mm')
        typeset.text(ImageDraw.Draw(second), (350, 60), 'Claude Code 3.0', self.face, '#222', 'mm')
        self.assertIsNone(ImageChops.difference(first, second).getbbox())

    def test_emoji_is_drawn_in_color_on_the_text_baseline(self):
        image = Image.new('RGBA', (800, 140))
        typeset.text(ImageDraw.Draw(image), (10, 100), 'apelido 😳', self.face, '#222', 'ls')
        self.assertGreater(yellow(image), 500)
        start = typeset.placed('apelido 😳', self.face, (10, 100), 'ls')[0][1][2]
        self.assertAlmostEqual(start, 10+self.face.getlength('apelido '), places=3)
        self.assertGreater(typeset.length('apelido 😳', self.face), self.face.getlength('apelido ')+self.face.size*.9)

    def test_title_block_wraps_and_reveals_emoji(self):
        obj = scene_layout.VisualObject(type='title', text='Claude Code 3.0\né só um apelido 😳', font_size=64,
                                        align='center', reveal='typing').model_dump()
        box = (0, 0, 700, 300)
        self.assertFalse(block_render.text_layout(obj, box, STYLE)[3])
        reveal = block_render.TextReveal(obj, box, STYLE, (700, 300), 3)
        self.assertEqual(reveal.characters, len('Claude Code 3.0')+len('é só um apelido 😳'))
        self.assertGreater(yellow(reveal.layer(None)), 500)
        self.assertEqual(yellow(reveal.layer(.1)), 0)

    def test_caption_word_with_emoji(self):
        image = Image.new('RGB', (1080, 1920), STYLE['background'])
        style = {**STYLE, 'captions': {'keywords': [], 'font_size': 72, 'position': 'bottom'}}
        captions.draw(image, {'words': ['Que', 'susto', '😳']}, style)
        self.assertGreater(yellow(image), 500)

    def test_flow_label_embeds_emoji_for_resvg(self):
        face = google_fonts.face('Roboto', 40)
        svg = flow.text(200, 80, 'Agente 😳', 40, '#29231F', face=face)
        self.assertIn('<image', svg)
        self.assertNotIn('😳', svg)
        layer = flow.rasterize(f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120" font-family="Roboto">{svg}</svg>',
                               str(google_fonts.install('Roboto')), 'Roboto')
        self.assertGreater(yellow(layer), 300)
        self.assertNotIn('<image', flow.text(200, 80, 'Agente', 40, '#29231F', face=face))


if __name__ == '__main__':
    unittest.main()
