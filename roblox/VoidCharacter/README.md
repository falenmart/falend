# Karakter Paketi: Sentry (Void) + Ken Kaneki

Karakter seçim menüsü (M tuşu / sol üst buton) ile güç seçilir. Seçince karakter ölür ve yeni güçle otomatik doğar.

## En kolay kurulum: CharacterPack.rbxmx
1. Studio'da Explorer'da **ServerStorage**'a sağ tıkla → **Insert from File...** → `CharacterPack.rbxmx`
2. Açılan `CharacterPack` klasörünün içindeki 3 klasörün **içindekileri** yazan yerlere sürükle:
   - `ReplicatedStorage -> ...` içindekiler → **ReplicatedStorage**
   - `ServerScriptService -> ...` içindekiler → **ServerScriptService**
   - `StarterPlayerScripts -> ...` içindekiler → **StarterPlayer > StarterPlayerScripts**
3. Eski VoidConfig / VoidServer / VoidClient'ı sil (yenileri onların yerine geçer), boş `CharacterPack` klasörünü sil.

## Dosyalar
| Dosya | Yer | Tür |
|---|---|---|
| CharacterList, RigPose, VoidConfig, KanekiConfig | ReplicatedStorage | ModuleScript |
| CharacterSelectServer, CombatServer, VoidServer, KanekiServer | ServerScriptService | Script |
| CharacterSelectClient, CombatClient, VoidClient, KanekiClient | StarterPlayerScripts | LocalScript |

## Tuşlar
**Sentry:** F uç · Z Void formu · X Kavrayış · C Dalga · G Boşluk (cutscene, Void formu gerekir)

**Kaneki:** E parmak kütlet + kagune aç/kapa · X Saplama · C Fırtına · V Yakalama (saldırılar için kagune açık olmalı)
Kagune açıkken durursan dokunaçlar kıvrılır, ara sıra kendiliğinden parmak kütletir.

**Herkes:** Sol tık = 4 vuruşluk kombo (basılı tut = art arda). Kaneki'de kagune açıksa dokunaçla savurur.

## Kagune 3D modelleri (isteğe bağlı)
`meshes/KaguneSegment.obj` ve `meshes/KaguneTip.obj` (`tools/make_kagune_meshes.py` ile üretildi).
1. Studio → Home/Avatar → **Import 3D** → `KaguneSegment.obj` → Import. Aynısını `KaguneTip.obj` için yap.
2. ReplicatedStorage içinde **KaguneMeshes** adında bir Folder oluştur.
3. Gelen MeshPart'ları bu klasöre taşı ve adlarını **Segment** ve **Tip** yap.
Klasör yoksa kagune basit şekillerle çizilir.
