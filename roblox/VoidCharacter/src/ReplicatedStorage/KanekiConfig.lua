-- KanekiConfig (ModuleScript) -> ReplicatedStorage
-- Kaneki karakterinin tüm ayarları.

local K = {}

K.Keys = {
	Kagune = Enum.KeyCode.E,  -- parmak kütlet + kaguneyi aç/kapa
	Strike = Enum.KeyCode.X,  -- dört dokunaçla öne saplama
	Flurry = Enum.KeyCode.C,  -- etrafa dokunaç fırtınası
	Grab = Enum.KeyCode.V,    -- hedefi yakala, havaya kaldır, yere çarp
}

K.Cooldowns = {
	Kagune = 3,
	Strike = 1.8,
	Flurry = 7,
	Grab = 10,
}

K.Strike = { Range = 22, ConeAngle = 40, Damage = 22, Knockback = 55 }
K.Flurry = { Radius = 16, Hits = 8, Interval = 0.18, Damage = 6 }
K.Grab = { Range = 28, ConeAngle = 45, LiftHeight = 8, Damage = 45 }

-- Kagune açıkken yürüme hızı
K.WalkSpeed = 22

-- Kagune açık ve karakter duruyorsa bu kadar saniye sonra kendiliğinden parmak kütletir
K.IdleCrackAfter = 7

-- Kagune görünümü
K.Kagune = {
	Length = 10,     -- dokunaç uzunluğu (stud)
	Segments = 18,   -- dokunaç başına parça sayısı (fazlası daha pürüzsüz ama daha ağır)
	BaseWidth = 1.2,
	TipWidth = 0.2,
	BaseColor = Color3.fromRGB(70, 0, 8),
	TipColor = Color3.fromRGB(230, 25, 40),
}
K.EyeColor = Color3.fromRGB(255, 20, 30)

-- Sesler (Roblox'un hazır sesleri; Toolbox'tan daha iyilerini "rbxassetid://NUMARA" ile koyabilirsin)
K.Sounds = {
	Crack = { Id = "rbxasset://sounds/clickfast.wav", Volume = 1.6, Speed = 1.5 },
	KaguneOut = { Id = "rbxasset://sounds/Rocket whoosh.wav", Volume = 1.2, Speed = 0.8 },
	KaguneIn = { Id = "rbxasset://sounds/swoosh.wav", Volume = 0.8, Speed = 0.7 },
	Strike = { Id = "rbxasset://sounds/swoosh.wav", Volume = 1.2, Speed = 1.3 },
	Hit = { Id = "rbxasset://sounds/collide.wav", Volume = 1, Speed = 0.9 },
	Flurry = { Id = "rbxasset://sounds/swoosh.wav", Volume = 0.9, Speed = 1.7 },
	Slam = { Id = "rbxasset://sounds/collide.wav", Volume = 2.2, Speed = 0.45 },
}

return K
