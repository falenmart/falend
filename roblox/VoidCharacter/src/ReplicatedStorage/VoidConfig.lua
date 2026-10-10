-- VoidConfig (ModuleScript) -> ReplicatedStorage
-- Tüm ayarlar burada. Hem server hem client bu modülü kullanır.

local Config = {}

-- Tuşlar
Config.Keys = {
	Fly = Enum.KeyCode.F,          -- uçmayı aç/kapa
	VoidForm = Enum.KeyCode.Z,     -- simsiyah form + beyaz gözler
	Grasp = Enum.KeyCode.X,        -- el uzat: tek hedefi gölgeye çevirip öldür
	Wave = Enum.KeyCode.C,         -- el uzat: önündeki konide gölge dalgası
	Ultimate = Enum.KeyCode.G,     -- CUTSCENE: herkesi gölgeye çevir (Void formu gerekir)
	FlyUp = Enum.KeyCode.Space,
	FlyDown = Enum.KeyCode.LeftControl,
	FlyBoost = Enum.KeyCode.LeftShift,
}

-- Bekleme süreleri (saniye)
Config.Cooldowns = {
	VoidForm = 2,
	Grasp = 6,
	Wave = 8,
	Ultimate = 30,
}

-- Uçuş
Config.FlySpeed = 55
Config.FlyBoostSpeed = 120

-- Skill: Void Grasp (X)
Config.Grasp = {
	Range = 70,
	ConeAngle = 35, -- derece
}

-- Skill: Void Wave (C)
Config.Wave = {
	Range = 45,
	ConeAngle = 50,
	Damage = 45,
}

-- Ultimate (G)
Config.Ultimate = {
	RequiresVoidForm = true,
	Radius = 90,
	RiseHeight = 16,
	-- Cutscene zaman çizelgesi (saniye)
	ArmsOpenAt = 2.0,
	ImpactAt = 7.2,
	EndAt = 10.5,
	-- Repliklerin çıkış zamanı ve metni (istediğin gibi değiştir)
	Lines = {
		{ At = 0.6, Text = "Herkes bir kahraman istedi..." },
		{ At = 3.0, Text = "Ama ışığın da bir gölgesi vardır." },
		{ At = 5.4, Text = "Ben Sentry değilim. Ben Boşluğum." },
	},
}

-- Görsel
Config.EyeColor = Color3.fromRGB(235, 245, 255)
Config.ShadowColor = Color3.fromRGB(5, 5, 8)

return Config
