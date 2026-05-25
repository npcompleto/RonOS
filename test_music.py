from tools.music_tool import _music_instance


search_result = _music_instance.search_any("Annalisa")
print(search_result)
_music_instance.play_any(search_result[0]['url'])
