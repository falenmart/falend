--[[
	YAMI SKILLS - AYARLAR (Config)
	Black Clover - Yami Sukehiro karanlık büyü seti.

	Buradaki her şeyi istediğin gibi değiştirebilirsin:
	  * tuşlar, bekleme süreleri (cooldown), hasar, menzil
	  * animasyon ID'leri (Roblox'a yükledikten sonra buraya yapıştır)
	  * ses ID'leri, parçacık dokuları, ekran efektleri
]]

local Config = {}

-- ============================================================ GENEL
Config.ToolName = "Yami Katana" -- envanterde görünen kılıç (Tool) adı
Config.GiveKatanaToEveryone = true -- true: herkes doğunca katanayı alır
Config.TeamCheck = false -- true: aynı takımdakilere hasar vermez
Config.DamageNPCs = true -- Humanoid'li NPC/dummy'lere hasar verilsin mi
Config.FlingUnanchoredParts = true -- büyük yeteneklerde sabitlenmemiş parçaları havaya uçur
Config.MaxFlingMass = 600
Config.Debug = false -- true: Output'a hitbox / istek bilgisi yazar

-- Tüm büyüler simsiyah. Accent sadece ince kontur / darbe karesi (impact frame) içindir.
Config.Theme = {
	Core = Color3.fromRGB(0, 0, 0),
	Deep = Color3.fromRGB(6, 4, 10),
	Accent = Color3.fromRGB(255, 255, 255),
	OutlineTransparency = 0.25, -- 1 yaparsan beyaz konturlar tamamen kapanır
}

-- ============================================================ TUŞLAR
-- M1 (sol tık / dokunma) = kılıç kombosu. Gamepad: R2.
Config.Keybinds = {
	BlackMoon = { Enum.KeyCode.Z, Enum.KeyCode.ButtonX },
	DeathThrust = { Enum.KeyCode.X, Enum.KeyCode.ButtonY },
	BlackCocoon = { Enum.KeyCode.C, Enum.KeyCode.ButtonB },
	DimensionSlash = { Enum.KeyCode.V, Enum.KeyCode.ButtonR1 },
	BlackBlade = { Enum.KeyCode.F, Enum.KeyCode.ButtonL1 },
}

-- HUD'da görünen sıra ve isimler
Config.SkillOrder = { "BlackMoon", "DeathThrust", "BlackCocoon", "DimensionSlash", "BlackBlade" }
Config.SkillNames = {
	M1 = "Kılıç Kombosu",
	BlackMoon = "Kara Hilal",
	DeathThrust = "Ölüm Saplaması",
	BlackCocoon = "Kara Koza",
	DimensionSlash = "Boyut Kesiği",
	BlackBlade = "Kara Kılıç",
}
Config.SkillSubtitles = {
	BlackMoon = "Kokugetsu",
	DeathThrust = "Yami Matoi: Shitotsu",
	BlackCocoon = "Ankoku Mayu",
	DimensionSlash = "Yami Matoi: Jigen Giri",
	BlackBlade = "Yami Matoi: Kokutō",
}

-- ============================================================ YETENEKLER
-- Süreler saniye, mesafeler stud. Zamanlamalar animasyonlarla eşleşir; değiştirirsen
-- animasyon ile efekt kayabilir.
Config.Skills = {
	M1 = {
		Interval = 0.36, -- iki tık arası en az süre
		ComboReset = 1.1, -- bu kadar beklenirse kombo 1'e döner
		FinisherCooldown = 0.9, -- 4. vuruştan sonra bekleme
		Animations = { "M1_1", "M1_2", "M1_3", "M1_4" },
		HitTime = { 0.15, 0.15, 0.15, 0.25 },
		Lock = { 0.34, 0.34, 0.34, 0.62 }, -- bu süre boyunca başka yetenek kullanılamaz
		Damage = { 6, 6, 7, 11 },
		Knockback = { 12, 12, 14, 60 },
		Launch = { 0, 0, 6, 34 },
		Stun = { 0.45, 0.45, 0.5, 0.9 },
		Range = 8,
		Width = 8,
		Height = 7,
		WalkSpeed = 9, -- vururken yürüme hızı
	},
	BlackMoon = { -- Kara Hilal: ileri uçan dev siyah hilal
		Cooldown = 6,
		Lock = 0.8,
		Animation = "BlackMoon",
		ReleaseTime = 0.37,
		Speed = 125,
		Range = 160,
		Width = 18,
		Height = 6,
		Damage = 22,
		Knockback = 70,
		Launch = 28,
		Stun = 0.8,
		WalkSpeed = 4,
	},
	DeathThrust = { -- Ölüm Saplaması: ileri atılıp delip geçer
		Cooldown = 8,
		Lock = 0.8,
		Animation = "DeathThrust",
		DashTime = 0.24,
		DashDuration = 0.26,
		DashSpeed = 105,
		Damage = 20,
		Knockback = 62,
		Launch = 22,
		Stun = 0.9,
		HitSize = Vector3.new(8, 8, 10),
		WalkSpeed = 0,
	},
	BlackCocoon = { -- Kara Koza: karanlık küre kalkanı, sonunda patlar
		Cooldown = 14,
		Animation = "BlackCocoon",
		ShellTime = 0.2,
		BurstTime = 2.45, -- kalkan bu ana kadar sürer, sonra patlar
		Lock = 2.75,
		Radius = 17,
		Damage = 18,
		Knockback = 75,
		Launch = 42,
		Stun = 1.0,
		ShellSize = 10,
	},
	DimensionSlash = { -- Boyut Kesiği: şarj + boyutu kesen dev siyah kesik
		Cooldown = 22,
		Animation = "DimensionSlash",
		SlashTime = 1.18,
		Lock = 2.1,
		Length = 150, -- kesiğin ileri menzili
		Width = 48,
		Height = 32,
		Damage = 50,
		Knockback = 32,
		Launch = 95, -- havalandırma gücü
		Stun = 1.6,
		RiftLength = 230, -- gökteki yarığın uzunluğu (görsel)
		RiftDistance = 24, -- yarığın karakterden uzaklığı (görsel)
		RiftTilt = 10, -- yarığın eğimi (derece)
		RiftOpenTime = 1.05, -- yarık açık kalma süresi
		WaveSpeed = 260, -- yeri parçalayan kesik dalgasının hızı
	},
	BlackBlade = { -- Kara Kılıç: kılıcı karanlıkla kaplar, hasar artar
		Cooldown = 25,
		Lock = 0.9,
		Animation = "BlackBlade",
		CoatTime = 0.5,
		Duration = 12,
		DamageMultiplier = 1.35,
	},
}

-- ============================================================ ANİMASYONLAR
--[[
	Animasyonlar Blender'da yapıldı ve ReplicatedStorage.YamiSkills.Animations içinde
	KeyframeSequence olarak geliyor.

	* ID'ler boşken: dahili animasyon oynatıcı KeyframeSequence'ları doğrudan oynatır
	  (Studio'da ve yayınlanmış oyunda çalışır, yüklemen gerekmez).
	* İstersen KeyframeSequence'a sağ tık -> "Save to Roblox..." ile yükle, çıkan ID'yi
	  aşağıya "rbxassetid://123456" şeklinde yapıştır. ID doluysa normal Animator kullanılır.
]]
Config.UseKeyframeFallback = true
Config.AnimationIds = {
	Hold = "",
	Equip = "",
	M1_1 = "",
	M1_2 = "",
	M1_3 = "",
	M1_4 = "",
	BlackMoon = "",
	DeathThrust = "",
	BlackCocoon = "",
	DimensionSlash = "",
	BlackBlade = "",
}
Config.EquipGrabTime = 0.14 -- Equip animasyonunda elin kabzayı tuttuğu an

-- ============================================================ MESHLER (Blender)
--[[
	Blender/Meshes klasöründeki FBX'leri Studio'da 3D Importer ile içe aktar ve oluşan
	MeshPart'ları ReplicatedStorage.YamiSkills.Assets.Meshes içine koy (alt klasörde olabilir).
	İsimleri değiştirme: SlashArc, DimensionRift, ShockRing, Swirl, Cocoon, Rock1, Rock2, Rock3,
	Shard, ImpactStar, Katana, KatanaSaya.
	Mesh yoksa script'ler aynı efektleri parçalarla (Part) yapar - yine çalışır.
	Bir mesh ters/yan görünüyorsa buradan derece cinsinden döndür (X, Y, Z).
]]
Config.UseMeshes = true
Config.MeshRotation = {
	SlashArc = Vector3.new(0, 0, 0),
	DimensionRift = Vector3.new(0, 0, 0),
	ShockRing = Vector3.new(0, 0, 0),
	Swirl = Vector3.new(0, 0, 0),
	Cocoon = Vector3.new(0, 0, 0),
	Shard = Vector3.new(0, 0, 0),
	ImpactStar = Vector3.new(0, 0, 0),
	Katana = Vector3.new(0, 0, 0),
	KatanaSaya = Vector3.new(0, 0, 0),
}

-- ============================================================ DOKULAR
-- Varsayılanlar Roblox'un içinde gelen dokular (yükleme gerekmez).
-- Blender/Textures içindeki P_*.png dosyalarını yükleyip ID'sini buraya yazarsan daha iyi görünür.
Config.Textures = {
	Smoke = "rbxasset://textures/particles/smoke_main.dds",
	Spark = "rbxasset://textures/particles/sparkles_main.dds",
	Shockwave = "rbxasset://textures/particles/explosion01_shockwave_main.dds",
	Implosion = "rbxasset://textures/particles/explosion01_implosion_main.dds",
	Glow = "rbxasset://textures/particles/forcefield_glow_main.dds",
	Vortex = "rbxasset://textures/particles/forcefield_vortex_main.dds",
	Square = "rbxasset://textures/particles/SquareParticle.png",
	-- isteğe bağlı (P_InkSmoke.png, P_Streak.png, P_Crack.png, P_Shards.png yükle):
	InkSmoke = "",
	Streak = "",
	Crack = "",
	Shards = "",
}

-- ============================================================ SESLER
-- Varsayılanlar Roblox içinde gelen sesler. Blender/Sounds klasöründeki .ogg dosyalarını
-- yükleyip Id'yi "rbxassetid://..." ile değiştirebilirsin (Speed/StartTime'ı 1 / 0 yap).
Config.Sounds = {
	Swing = { Id = "rbxasset://sounds/action_falling.ogg", Volume = 0.9, Speed = 2.6, StartTime = 0.2, Duration = 0.3 },
	HeavySwing = {
		Id = "rbxasset://sounds/action_falling.ogg",
		Volume = 1.1,
		Speed = 1.7,
		StartTime = 0.2,
		Duration = 0.45,
	},
	Hit = { Id = "rbxasset://sounds/action_jump_land.mp3", Volume = 1.0, Speed = 1.5 },
	HeavyHit = { Id = "rbxasset://sounds/impact_explosion_03.mp3", Volume = 0.8, Speed = 1.4 },
	Boom = { Id = "rbxasset://sounds/impact_explosion_03.mp3", Volume = 1.3, Speed = 0.6, Reverb = true },
	Rift = { Id = "rbxasset://sounds/impact_explosion_03.mp3", Volume = 1.6, Speed = 0.38, Reverb = true },
	Charge = { Id = "rbxasset://sounds/action_falling.ogg", Volume = 0.8, Speed = 0.45, Looped = true },
	Dash = { Id = "rbxasset://sounds/action_falling.ogg", Volume = 1.0, Speed = 3.0, StartTime = 0.1, Duration = 0.35 },
	Draw = { Id = "rbxasset://sounds/action_get_up.mp3", Volume = 0.7, Speed = 1.8 },
	Coat = { Id = "rbxasset://sounds/action_swim.mp3", Volume = 0.9, Speed = 0.5 },
	Shell = { Id = "rbxasset://sounds/action_swim.mp3", Volume = 1.0, Speed = 0.35 },
}

-- ============================================================ EKRAN / KAMERA
Config.Screen = {
	Shake = true,
	ShakeMultiplier = 1,
	ImpactFrames = true, -- manga tarzı siyah-beyaz darbe kareleri
	ScreenSlash = true, -- boyut kesiğinde ekranı kesen çizgi
	ColorEffects = true,
	FieldOfViewKick = true,
	EffectRadius = 220, -- başkasının yeteneği bu mesafedeyse ekran efektleri sende de olur
}

return Config
