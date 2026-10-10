# Void Karakteri (Roblox)

Sentry'nin "Void" formundan esinlenen karakter: uçma, simsiyah Void formu, el uzatarak kullanılan skiller ve cutscene'li ultimate.

## Kurulum (Studio)
| Dosya | Studio'da nereye | Tür |
|---|---|---|
| `src/ReplicatedStorage/VoidConfig.lua` | ReplicatedStorage → adı `VoidConfig` | **ModuleScript** |
| `src/ServerScriptService/VoidServer.server.lua` | ServerScriptService → `VoidServer` | **Script** |
| `src/StarterPlayerScripts/VoidClient.client.lua` | StarterPlayer → StarterPlayerScripts → `VoidClient` | **LocalScript** |

Game Settings → Avatar → **R15** önerilir (R6 da çalışır). Rojo kullanıyorsan: `rojo serve`.

## Tuşlar
| Tuş | Skill |
|---|---|
| F | Uç / in (Space yukarı, Ctrl aşağı, Shift hızlan) |
| Z | Void formu: simsiyah beden, hafif beyaz gözler, siyah duman aurası |
| X | Kavrayış: elini uzatır, öndeki hedefi gölge dokunaçlarıyla kaldırır, gölgeye çevirip öldürür |
| C | Dalga: elini uzatır, önündeki koniye gölge dalgası (hasar, ölen duman olur) |
| G | **Ultimate (Void formu gerekli):** cutscene, havaya yükselir, kollarını açar, replikleri söyler, çevresindeki herkes siyah gölge/duman olup ölür |

NPC'ler de hasar alır: içinde `Humanoid` olan her Model hedeftir.
Replikler, süreler, hasar, menzil ve tuşlar `VoidConfig` içinden değiştirilebilir.
