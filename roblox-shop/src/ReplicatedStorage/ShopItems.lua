-- ShopItems (ModuleScript)
-- Konum: ReplicatedStorage > ShopItems
--
-- Mağazadaki tüm eşyalar, kategoriler ve ayarlar burada.
-- Yeni eşya eklemek için Items listesine bir satır eklemen yeterli.

local ShopItems = {}

ShopItems.Settings = {
	CurrencyName = "Coins", -- leaderstats içindeki para birimi adı
	CoinIcon = "🪙", -- Kutucuk görünürse "💰" yap
	StartingCoins = 1000, -- Yeni oyuncunun başlangıç parası
	PassiveIncome = { Amount = 25, Interval = 60 }, -- Her 60 saniyede +25 coin (Amount = 0 kapatır)
	AutoEquipOnPurchase = true, -- Satın alınca otomatik kuşan
	DefaultWalkSpeed = 16,
	DefaultJumpPower = 50,
	DataStoreName = "ShopData_v1",
	ToggleKey = Enum.KeyCode.M, -- Mağazayı aç/kapat tuşu

	-- Robux ile coin satmak istersen bir Developer Product oluşturup ID'sini yaz.
	-- 0 bırakırsan header'daki "+" butonu sadece bilgi mesajı gösterir.
	CoinProduct = { Id = 0, Amount = 1000 },
}

ShopItems.Rarities = {
	Common = { Name = "Sıradan", Color = Color3.fromRGB(154, 163, 192) },
	Rare = { Name = "Nadir", Color = Color3.fromRGB(77, 163, 255) },
	Epic = { Name = "Epik", Color = Color3.fromRGB(178, 107, 255) },
	Legendary = { Name = "Efsanevi", Color = Color3.fromRGB(255, 176, 32) },
}

ShopItems.Categories = {
	{ Id = "Weapons", Name = "Silahlar", Icon = "⚔️" },
	{ Id = "Powers", Name = "Güçler", Icon = "⚡" },
	{ Id = "Pets", Name = "Evcil Hayvan", Icon = "🐾" },
	{ Id = "Effects", Name = "Efektler", Icon = "✨" },
}

--[[
	Eşya alanları:
	  Id          benzersiz isim (Silahlarda ServerStorage.ShopTools içindeki Tool'un adı)
	  Category    Categories içindeki Id
	  Name, Icon  ekranda görünen isim ve emoji
	  Image       (isteğe bağlı) "rbxassetid://123" verirsen emoji yerine resim gösterilir
	  Rarity      Common / Rare / Epic / Legendary
	  Price       fiyat (0 = herkese ücretsiz verilir)
	  New         true ise kartta "YENİ" rozeti çıkar
	  Stats       detay panelindeki satırlar: { {"Başlık", "Değer"}, ... }

	  Tool = true                    -> ServerStorage.ShopTools[Id] oyuncuya verilir
	  Boost = { WalkSpeed, JumpPower, CoinMultiplier }
	  Pet = true                     -> karakterin yanında uçan emoji evcil hayvan
	  Effect = "Fire" | "Sparkles" | "Smoke", EffectProps = { ... }
]]
ShopItems.Items = {
	-- Silahlar
	{ Id = "WoodenSword", Category = "Weapons", Name = "Tahta Kılıç", Icon = "🗡️", Rarity = "Common", Price = 0, Tool = true,
		Description = "Her maceracının ilk silahı. Hafif ve kullanışlı.",
		Stats = { { "Hasar", "10" }, { "Hız", "Hızlı" } } },
	{ Id = "BattleAxe", Category = "Weapons", Name = "Savaş Baltası", Icon = "🪓", Rarity = "Common", Price = 250, Tool = true,
		Description = "Ağır ama güçlü darbeler indiren klasik bir balta.",
		Stats = { { "Hasar", "20" }, { "Hız", "Orta" } } },
	{ Id = "HunterBow", Category = "Weapons", Name = "Okçu Yayı", Icon = "🏹", Rarity = "Rare", Price = 600, Tool = true,
		Description = "Düşmanlarını uzaktan vurmanı sağlayan hassas bir yay.",
		Stats = { { "Hasar", "18" }, { "Menzil", "Uzun" } } },
	{ Id = "ThorHammer", Category = "Weapons", Name = "Thor'un Çekici", Icon = "🔨", Rarity = "Epic", Price = 1500, Tool = true, New = true,
		Description = "Yere vurduğunda etrafındaki herkesi geri savuran efsanevi gök gürültüsü çekici.",
		Stats = { { "Hasar", "45" }, { "Hız", "Yavaş" } } },
	{ Id = "DualSwords", Category = "Weapons", Name = "Çift Kılıç", Icon = "⚔️", Rarity = "Rare", Price = 900, Tool = true,
		Description = "İki elinle aynı anda saldır, rakiplerine nefes aldırma.",
		Stats = { { "Hasar", "2x15" }, { "Hız", "Çok Hızlı" } } },
	{ Id = "SeaTrident", Category = "Weapons", Name = "Deniz Mızrağı", Icon = "🔱", Rarity = "Legendary", Price = 5000, Tool = true,
		Description = "Okyanusların gücünü taşıyan efsanevi mızrak.",
		Stats = { { "Hasar", "70" }, { "Özel", "Dalga" } } },

	-- Güçler
	{ Id = "RunningShoes", Category = "Powers", Name = "Koşu Ayakkabısı", Icon = "👟", Rarity = "Common", Price = 300,
		Boost = { WalkSpeed = 22 },
		Description = "Haritada daha hızlı dolaşmanı sağlar.",
		Stats = { { "Yürüme Hızı", "22" } } },
	{ Id = "SuperJump", Category = "Powers", Name = "Süper Zıplama", Icon = "🦘", Rarity = "Rare", Price = 700,
		Boost = { JumpPower = 80 },
		Description = "Kangurular bile seni kıskanacak!",
		Stats = { { "Zıplama Gücü", "80" } } },
	{ Id = "Rocket", Category = "Powers", Name = "Roket Hızı", Icon = "🚀", Rarity = "Epic", Price = 2000,
		Boost = { WalkSpeed = 32 },
		Description = "Rüzgar gibi koş, kimse sana yetişemesin.",
		Stats = { { "Yürüme Hızı", "32" } } },
	{ Id = "DoubleCoins", Category = "Powers", Name = "2x Coin", Icon = "💰", Rarity = "Legendary", Price = 4000,
		Boost = { CoinMultiplier = 2 },
		Description = "Pasif gelirden kazandığın coinler iki katına çıkar.",
		Stats = { { "Coin Çarpanı", "x2" } } },

	-- Evcil Hayvanlar
	{ Id = "Dog", Category = "Pets", Name = "Köpüş", Icon = "🐶", Rarity = "Common", Price = 400, Pet = true,
		Description = "Sadık dostun, her yerde peşinden gelir.", Stats = { { "Sadakat", "★★★★★" } } },
	{ Id = "Cat", Category = "Pets", Name = "Pamuk", Icon = "🐱", Rarity = "Common", Price = 400, Pet = true,
		Description = "Biraz nazlı ama çok tatlı bir kedi.", Stats = { { "Tatlılık", "★★★★★" } } },
	{ Id = "Fox", Category = "Pets", Name = "Tilki", Icon = "🦊", Rarity = "Rare", Price = 1000, Pet = true,
		Description = "Kurnaz ve hızlı bir orman dostu.", Stats = { { "Kurnazlık", "★★★★☆" } } },
	{ Id = "Panda", Category = "Pets", Name = "Panda", Icon = "🐼", Rarity = "Rare", Price = 1200, Pet = true,
		Description = "Bambu sever, uykucu ve sevimli.", Stats = { { "Uykuculuk", "★★★★★" } } },
	{ Id = "Unicorn", Category = "Pets", Name = "Unicorn", Icon = "🦄", Rarity = "Epic", Price = 3000, Pet = true,
		Description = "Gökkuşağından gelen büyülü bir dost.", Stats = { { "Büyü", "★★★★☆" } } },
	{ Id = "Dragon", Category = "Pets", Name = "Ejderha", Icon = "🐉", Rarity = "Legendary", Price = 7500, Pet = true, New = true,
		Description = "Sunucudaki herkesin gözü onda olacak.", Stats = { { "Güç", "★★★★★" } } },

	-- Efektler
	{ Id = "Sparkle", Category = "Effects", Name = "Işıltı", Icon = "✨", Rarity = "Common", Price = 350,
		Effect = "Sparkles", EffectProps = { SparkleColor = Color3.fromRGB(255, 230, 120) },
		Description = "Karakterinin etrafında parıltılar uçuşur." },
	{ Id = "SmokeTrail", Category = "Effects", Name = "Duman", Icon = "💨", Rarity = "Rare", Price = 800,
		Effect = "Smoke", EffectProps = { Color = Color3.fromRGB(200, 200, 220), Opacity = 0.15, RiseVelocity = 2, Size = 1 },
		Description = "Gizemli bir duman bulutuyla dolaş." },
	{ Id = "FireAura", Category = "Effects", Name = "Ateş Aurası", Icon = "🔥", Rarity = "Epic", Price = 2500,
		Effect = "Fire", EffectProps = { Heat = 5, Size = 4 },
		Description = "Alevler içinde yürü, herkes geri çekilsin." },
	{ Id = "PurpleFlame", Category = "Effects", Name = "Mor Alev", Icon = "💜", Rarity = "Legendary", Price = 6000,
		Effect = "Fire", EffectProps = { Heat = 6, Size = 5, Color = Color3.fromRGB(170, 80, 255), SecondaryColor = Color3.fromRGB(255, 120, 220) },
		Description = "Sadece en zenginlerin taşıyabildiği efsanevi alev." },
}

ShopItems.ById = {}
for index, item in ipairs(ShopItems.Items) do
	item.Order = index
	ShopItems.ById[item.Id] = item
end

return ShopItems
