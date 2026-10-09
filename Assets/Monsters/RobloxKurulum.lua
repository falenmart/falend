--[[
	RobloxKurulum.lua  -  Fisilti / GeriDonen / Bakan canavarlarini Roblox'a hazirlar.

	KULLANIM (Roblox Studio):
	  1) Avatar/Home > Import 3D ile FBX'i ice aktar (Fisilti.fbx, GeriDonen.fbx, Bakan.fbx).
	     Model Workspace'e "Fisilti" / "GeriDonen" / "Bakan" adiyla gelir.
	  2) View > Command Bar'i ac, bu dosyanin TAMAMINI yapistir ve Enter'a bas.

	Betik, Workspace'te (veya seciliyse Selection'da) buldugu her canavar icin:
	  - Importer'in olusturdugu ic ice hiyerarsiyi duzlestirir, eksik parca varsa uyarir
	  - Boyu Blender'daki olcuye (stud) getirir, on yonunu Root'un LookVector'una esitler
	  - Renk / Material (Neon dahil) / saydamlik ayarlarini yapar
	  - Tum parcalari Root'a kaynaklar (Root Anchored, PrimaryPart)
	  - Fisilti: Govde'ye Trail (siyah iz) + Attachment'lar, yuz/agiz isigi, duman
	  - GeriDonen: catlak isiklari, kuyruk dumani
	  - Bakan: irisler (Motor6D) oyuncuyu takip eder, halkalar yavasca doner, mor isik
	  - Modeli ReplicatedStorage/Assets/Monsters/<Ad> konumuna tasir
	Tekrar calistirmak guvenlidir (once eski efektleri temizler).
]]

local HEDEF_SERVIS = game:GetService("ReplicatedStorage") -- istersen ServerStorage yap
local Selection = game:GetService("Selection")

local function rgb(r, g, b)
	return Color3.fromRGB(r, g, b)
end

local function liste(onek, ilk, son)
	local t = {}
	for i = ilk, son do
		table.insert(t, onek .. i)
	end
	return t
end

local function birlestir(...)
	local t = {}
	for _, l in ipairs({ ... }) do
		for _, v in ipairs(l) do
			table.insert(t, v)
		end
	end
	return t
end

----------------------------------------------------------------------------
-- Canavar tanimlari (olculer Blender'daki modelden: 1 birim = 1 stud)
----------------------------------------------------------------------------
local SIYAH = { Material = Enum.Material.SmoothPlastic, Color = rgb(12, 12, 14) }

local CANAVARLAR = {
	Fisilti = {
		olcuParcalari = nil, -- nil = Root disindaki tum parcalar
		olcuEkseni = "Y",
		hedefOlcu = 9.0, -- boy
		yerdenBosluk = 1.0, -- en alt nokta yerden 1 stud yukarida
		onParca = "Yuz",
		parcalar = birlestir({ "Root", "Govde", "Bas", "Yuz", "Agiz", "SolKol", "SagKol" }, liste("Pelerin", 1, 6)),
		gorunum = {
			Govde = SIYAH,
			Bas = SIYAH,
			SolKol = SIYAH,
			SagKol = SIYAH,
			Pelerin = { Material = Enum.Material.SmoothPlastic, Color = rgb(8, 8, 10), Transparency = 0.05 },
			Yuz = { Material = Enum.Material.Neon, Color = rgb(225, 232, 255), Transparency = 0.3, CastShadow = false },
			Agiz = { Material = Enum.Material.Neon, Color = rgb(255, 95, 85), Transparency = 0.1, CastShadow = false },
		},
	},
	GeriDonen = {
		olcuParcalari = nil,
		olcuEkseni = "Y",
		hedefOlcu = 10.0,
		yerdenBosluk = 0.5,
		onParca = "BasOn",
		parcalar = birlestir({ "Root", "Govde", "BasOn", "BasArka", "Catlaklar" }, liste("Kol", 1, 4), liste("Kuyruk", 1, 4)),
		gorunum = {
			Govde = { Material = Enum.Material.SmoothPlastic, Color = rgb(42, 8, 13), Reflectance = 0.03 },
			BasOn = { Material = Enum.Material.SmoothPlastic, Color = rgb(42, 8, 13), Reflectance = 0.03 },
			BasArka = { Material = Enum.Material.SmoothPlastic, Color = rgb(42, 8, 13), Reflectance = 0.03 },
			Kol = { Material = Enum.Material.SmoothPlastic, Color = rgb(36, 7, 11) },
			Kuyruk = { Material = Enum.Material.SmoothPlastic, Color = rgb(24, 5, 8), Transparency = 0.12 },
			Catlaklar = { Material = Enum.Material.Neon, Color = rgb(255, 110, 25), CastShadow = false },
		},
	},
	Bakan = {
		-- cap: goz kumesi (kutle + gozler), halkalar haric
		olcuParcalari = birlestir({ "Kutle", "AnaGoz", "AnaIris" }, liste("KucukGoz", 1, 15), liste("Iris", 1, 15)),
		olcuEkseni = "MAX",
		hedefOlcu = 6.0,
		yerdenBosluk = nil, -- serbest suzulur
		onParca = "AnaGoz",
		parcalar = birlestir(
			{ "Root", "AnaGoz", "AnaIris", "Kutle", "Parilti", "Halka1", "Halka2", "Halka3" },
			liste("KucukGoz", 1, 15),
			liste("Iris", 1, 15)
		),
		gorunum = {
			Kutle = { Material = Enum.Material.SmoothPlastic, Color = rgb(26, 8, 36), Reflectance = 0.06 },
			AnaGoz = { Material = Enum.Material.SmoothPlastic, Color = rgb(240, 233, 226), dokuyuKoru = true },
			KucukGoz = { Material = Enum.Material.SmoothPlastic, Color = rgb(240, 233, 226), dokuyuKoru = true },
			AnaIris = { Material = Enum.Material.SmoothPlastic, Color = rgb(6, 5, 7), Reflectance = 0.15 },
			Iris = { Material = Enum.Material.SmoothPlastic, Color = rgb(6, 5, 7), Reflectance = 0.15 },
			Halka = { Material = Enum.Material.Metal, Color = rgb(12, 12, 15) },
			Parilti = { Material = Enum.Material.Neon, Color = rgb(140, 45, 255), Transparency = 0.82, CastShadow = false },
		},
	},
}

----------------------------------------------------------------------------
-- Bakan istemci betigi: irisler yerel oyuncuyu izler, halkalar doner
----------------------------------------------------------------------------
local BAKAN_BETIK = [==[
-- BakanBakis (RunContext = Client): her oyuncu, gozlerin KENDISINE baktigini gorur.
local RunService = game:GetService("RunService")
local Players = game:GetService("Players")

local model = script.Parent
while not model:IsDescendantOf(workspace) do
	model.AncestryChanged:Wait()
end

local root = model:WaitForChild("Root")
local MENZIL = 80 -- bu mesafeden uzaktaki oyuncuya bakmaz
local HIZ = 8 -- iris donus yumusakligi

local gozler, halkalar = {}, {}
for _, m in ipairs(model:GetDescendants()) do
	if m:IsA("Motor6D") and m.Name == "IrisMotor" then
		table.insert(gozler, {
			motor = m,
			goz = m.Part0,
			dinlenme = m:GetAttribute("DinlenmeYonu"),
			maks = math.rad(m:GetAttribute("MaksAci") or 30),
			simdiki = CFrame.identity,
		})
	elseif m:IsA("Motor6D") and m.Name == "HalkaMotor" then
		table.insert(halkalar, {
			motor = m,
			eksen = m:GetAttribute("Eksen"),
			hiz = m:GetAttribute("Hiz"),
			aci = 0,
		})
	end
end

local oyuncu = Players.LocalPlayer

RunService.RenderStepped:Connect(function(dt)
	local karakter = oyuncu.Character
	local bas = karakter and karakter:FindFirstChild("Head")
	local hedef = bas and bas.Position
	if hedef and (hedef - root.Position).Magnitude > MENZIL then
		hedef = nil
	end

	local k = math.clamp(dt * HIZ, 0, 1)
	for _, g in ipairs(gozler) do
		local amac = CFrame.identity
		if hedef and g.dinlenme then
			local yon = g.goz.CFrame:VectorToObjectSpace(hedef - g.goz.Position)
			if yon.Magnitude > 1e-3 then
				yon = yon.Unit
				local eksen = g.dinlenme:Cross(yon)
				local aci = math.acos(math.clamp(g.dinlenme:Dot(yon), -1, 1))
				if eksen.Magnitude > 1e-4 then
					amac = CFrame.fromAxisAngle(eksen.Unit, math.min(aci, g.maks))
				end
			end
		end
		g.simdiki = g.simdiki:Lerp(amac, k)
		g.motor.C0 = g.simdiki
	end

	for _, h in ipairs(halkalar) do
		h.aci = (h.aci + h.hiz * dt) % (2 * math.pi)
		h.motor.C0 = CFrame.fromAxisAngle(h.eksen, h.aci)
	end
end)
]==]

----------------------------------------------------------------------------
-- Yardimcilar
----------------------------------------------------------------------------
local function gorunumBul(cfg, ad)
	if cfg.gorunum[ad] then
		return cfg.gorunum[ad]
	end
	local onek = string.match(ad, "^(%a+)%d+$")
	return onek and cfg.gorunum[onek]
end

local function kapsam(parcalar)
	local mn = Vector3.new(math.huge, math.huge, math.huge)
	local mx = -mn
	for _, p in ipairs(parcalar) do
		local h = p.Size / 2
		for _, sx in ipairs({ -1, 1 }) do
			for _, sy in ipairs({ -1, 1 }) do
				for _, sz in ipairs({ -1, 1 }) do
					local w = p.CFrame:PointToWorldSpace(Vector3.new(h.X * sx, h.Y * sy, h.Z * sz))
					mn = mn:Min(w)
					mx = mx:Max(w)
				end
			end
		end
	end
	return mn, mx
end

local function duzlestir(model)
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and d.Parent ~= model then
			d.Parent = model
		end
	end
	for _, c in ipairs(model:GetChildren()) do
		if not c:IsA("BasePart") and not c:IsA("Script") and #c:GetDescendants() == 0 then
			c:Destroy()
		end
	end
end

local function temizle(model)
	for _, d in ipairs(model:GetDescendants()) do
		if d:GetAttribute("CanavarKurulum") then
			d:Destroy()
		end
	end
end

local function isaretle(inst)
	inst:SetAttribute("CanavarKurulum", true)
	return inst
end

local function parcaBul(model, ad)
	local p = model:FindFirstChild(ad)
	if p and p:IsA("BasePart") then
		return p
	end
	return nil
end

local function klasor(ust, ad)
	local f = ust:FindFirstChild(ad)
	if not f then
		f = Instance.new("Folder")
		f.Name = ad
		f.Parent = ust
	end
	return f
end

----------------------------------------------------------------------------
-- Kurulum
----------------------------------------------------------------------------
local function kur(model, ad, cfg)
	duzlestir(model)
	temizle(model)

	local eksik = {}
	for _, p in ipairs(cfg.parcalar) do
		if not parcaBul(model, p) then
			table.insert(eksik, p)
		end
	end
	if #eksik > 0 then
		warn(ad .. ": eksik parca(lar): " .. table.concat(eksik, ", "))
	end
	local root = parcaBul(model, "Root")
	if not root then
		warn(ad .. ": Root bulunamadi, atlandi.")
		return
	end
	model.PrimaryPart = root

	local tumParcalar = {}
	for _, c in ipairs(model:GetChildren()) do
		if c:IsA("BasePart") and c ~= root then
			table.insert(tumParcalar, c)
		end
	end

	-- 1) Olcek: importer birimlerinden bagimsiz olarak Blender olcusune getir
	local olcuListesi = tumParcalar
	if cfg.olcuParcalari then
		olcuListesi = {}
		for _, n in ipairs(cfg.olcuParcalari) do
			local p = parcaBul(model, n)
			if p then
				table.insert(olcuListesi, p)
			end
		end
	end
	local mn, mx = kapsam(olcuListesi)
	local boyut = mx - mn
	local simdiki = cfg.olcuEkseni == "Y" and boyut.Y or math.max(boyut.X, boyut.Y, boyut.Z)
	if simdiki > 0 then
		model:ScaleTo(model:GetScale() * (cfg.hedefOlcu / simdiki))
	end

	-- 2) Yon: Root'un LookVector'u canavarin onune baksin (parcalar yerinde kalir)
	local on = parcaBul(model, cfg.onParca)
	if on then
		local fark = on.Position - root.Position
		local duz = Vector3.new(fark.X, 0, fark.Z)
		if duz.Magnitude < 1e-3 then
			duz = Vector3.new(0, 0, -1)
		end
		root.CFrame = CFrame.lookAt(root.Position, root.Position + duz.Unit)
	end
	model.WorldPivot = root.CFrame

	-- 3) Gorunum + fizik
	for _, p in ipairs(tumParcalar) do
		local g = gorunumBul(cfg, p.Name)
		if g then
			p.Material = g.Material
			p.Color = g.Color
			p.Transparency = g.Transparency or 0
			p.Reflectance = g.Reflectance or 0
			if g.CastShadow ~= nil then
				p.CastShadow = g.CastShadow
			end
			if not g.dokuyuKoru then
				for _, sa in ipairs(p:GetChildren()) do
					if sa:IsA("SurfaceAppearance") then
						sa:Destroy()
					end
				end
				if p:IsA("MeshPart") then
					p.TextureID = ""
				end
			end
		end
		p.Anchored = false
		p.CanCollide = false
		p.CanQuery = false
		p.CanTouch = false
		p.Massless = true
	end
	root.Transparency = 1
	root.Anchored = true
	root.CanCollide = false
	root.CanQuery = true
	root.CanTouch = true
	root.Massless = false

	-- 4) Baglantilar: hareketli parcalar Motor6D, digerleri WeldConstraint
	local motorlu = {}
	if ad == "Bakan" then
		local function irisMotoru(gozAd, irisAd, maks)
			local goz, iris = parcaBul(model, gozAd), parcaBul(model, irisAd)
			if not (goz and iris) then
				return
			end
			local m = isaretle(Instance.new("Motor6D"))
			m.Name = "IrisMotor"
			m.Part0 = goz
			m.Part1 = iris
			m.C0 = CFrame.identity
			m.C1 = iris.CFrame:Inverse() * goz.CFrame
			local yon = goz.CFrame:PointToObjectSpace(iris.Position)
			m:SetAttribute("DinlenmeYonu", yon.Magnitude > 0 and yon.Unit or Vector3.new(0, 0, -1))
			m:SetAttribute("MaksAci", maks)
			m.Parent = iris
			motorlu[iris] = true
		end
		irisMotoru("AnaGoz", "AnaIris", 30)
		for i = 1, 15 do
			irisMotoru("KucukGoz" .. i, "Iris" .. i, 26)
		end
		local eksenler = {
			{ Vector3.new(0, 1, 0), 0.22 },
			{ Vector3.new(1, 0.35, 0).Unit, -0.16 },
			{ Vector3.new(0.2, 0.4, 1).Unit, 0.12 },
		}
		for i, e in ipairs(eksenler) do
			local h = parcaBul(model, "Halka" .. i)
			if h then
				local m = isaretle(Instance.new("Motor6D"))
				m.Name = "HalkaMotor"
				m.Part0 = root
				m.Part1 = h
				m.C0 = CFrame.identity
				m.C1 = h.CFrame:Inverse() * root.CFrame
				m:SetAttribute("Eksen", e[1])
				m:SetAttribute("Hiz", e[2]) -- rad/sn
				m.Parent = h
				motorlu[h] = true
			end
		end
	end
	for _, p in ipairs(tumParcalar) do
		if not motorlu[p] then
			local w = isaretle(Instance.new("WeldConstraint"))
			w.Name = "RootKaynak"
			w.Part0 = root
			w.Part1 = p
			w.Parent = p
		end
	end

	-- 5) Efektler
	if ad == "Fisilti" then
		local govde = parcaBul(model, "Govde")
		if govde then
			local ust = isaretle(Instance.new("Attachment"))
			ust.Name = "IzUst"
			ust.Position = Vector3.new(0, govde.Size.Y * 0.3, 0)
			ust.Parent = govde
			local alt = isaretle(Instance.new("Attachment"))
			alt.Name = "IzAlt"
			alt.Position = Vector3.new(0, -govde.Size.Y * 0.35, 0)
			alt.Parent = govde

			local trail = isaretle(Instance.new("Trail"))
			trail.Name = "SiyahIz"
			trail.Attachment0 = ust
			trail.Attachment1 = alt
			trail.Color = ColorSequence.new(Color3.new(0, 0, 0))
			trail.Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 0.1),
				NumberSequenceKeypoint.new(0.6, 0.6),
				NumberSequenceKeypoint.new(1, 1),
			})
			trail.WidthScale = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1),
				NumberSequenceKeypoint.new(1, 0.3),
			})
			trail.Lifetime = 0.6
			trail.MinLength = 0.05
			trail.LightEmission = 0
			trail.LightInfluence = 0
			trail.FaceCamera = true
			trail.Enabled = true
			trail.Parent = govde

			local duman = isaretle(Instance.new("ParticleEmitter"))
			duman.Name = "Duman"
			duman.Texture = "rbxasset://textures/particles/smoke_main.dds"
			duman.Color = ColorSequence.new(Color3.new(0, 0, 0))
			duman.Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1),
				NumberSequenceKeypoint.new(0.2, 0.6),
				NumberSequenceKeypoint.new(1, 1),
			})
			duman.Size = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1.2),
				NumberSequenceKeypoint.new(1, 3),
			})
			duman.Lifetime = NumberRange.new(1, 1.8)
			duman.Rate = 8
			duman.Speed = NumberRange.new(0.3, 0.8)
			duman.SpreadAngle = Vector2.new(180, 180)
			duman.LightInfluence = 0
			duman.Parent = govde
		end
		local yuz = parcaBul(model, "Yuz")
		if yuz then
			local l = isaretle(Instance.new("PointLight"))
			l.Name = "YuzIsigi"
			l.Color = rgb(220, 230, 255)
			l.Brightness = 0.8
			l.Range = 7
			l.Shadows = false
			l.Parent = yuz
		end
		local agiz = parcaBul(model, "Agiz")
		if agiz then
			local l = isaretle(Instance.new("PointLight"))
			l.Name = "AgizIsigi"
			l.Color = rgb(255, 70, 60)
			l.Brightness = 0.6
			l.Range = 4
			l.Shadows = false
			l.Parent = agiz
		end
	elseif ad == "GeriDonen" then
		local govde = parcaBul(model, "Govde")
		if govde then
			for i, y in ipairs({ 0.25, -0.15 }) do
				local a = isaretle(Instance.new("Attachment"))
				a.Name = "CatlakIsik" .. i
				a.Position = Vector3.new(0, govde.Size.Y * y, 0)
				a.Parent = govde
				local l = isaretle(Instance.new("PointLight"))
				l.Color = rgb(255, 110, 30)
				l.Brightness = 1.2
				l.Range = 10
				l.Shadows = false
				l.Parent = a
			end
			local alt = isaretle(Instance.new("Attachment"))
			alt.Name = "KuyrukDuman"
			alt.Position = Vector3.new(0, -govde.Size.Y * 0.5, 0)
			alt.Parent = govde
			local duman = isaretle(Instance.new("ParticleEmitter"))
			duman.Name = "Duman"
			duman.Texture = "rbxasset://textures/particles/smoke_main.dds"
			duman.Color = ColorSequence.new(rgb(25, 4, 6))
			duman.Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1),
				NumberSequenceKeypoint.new(0.25, 0.55),
				NumberSequenceKeypoint.new(1, 1),
			})
			duman.Size = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1.5),
				NumberSequenceKeypoint.new(1, 3.5),
			})
			duman.Lifetime = NumberRange.new(1.2, 2)
			duman.Rate = 10
			duman.Speed = NumberRange.new(0.5, 1.2)
			duman.EmissionDirection = Enum.NormalId.Bottom
			duman.SpreadAngle = Vector2.new(35, 35)
			duman.LightInfluence = 0
			duman.Parent = alt
		end
	elseif ad == "Bakan" then
		local l = isaretle(Instance.new("PointLight"))
		l.Name = "MorParilti"
		l.Color = rgb(150, 60, 255)
		l.Brightness = 1.5
		l.Range = 14
		l.Shadows = false
		l.Parent = root

		local eski = model:FindFirstChild("BakanBakis")
		if eski then
			eski:Destroy()
		end
		local s = isaretle(Instance.new("Script"))
		s.Name = "BakanBakis"
		s.RunContext = Enum.RunContext.Client
		s.Source = BAKAN_BETIK
		s.Parent = model
	end

	-- 6) Oyun kodu icin bilgi: Root merkezinin zeminden yuksekligi
	local amn = kapsam(tumParcalar)
	if cfg.yerdenBosluk then
		model:SetAttribute("RootYerdenYukseklik", root.Position.Y - amn.Y + cfg.yerdenBosluk)
	end
	model:SetAttribute("Canavar", ad)

	-- 7) Assets/Monsters/<Ad>
	local hedef = klasor(klasor(HEDEF_SERVIS, "Assets"), "Monsters")
	local eskiKopya = hedef:FindFirstChild(ad)
	if eskiKopya and eskiKopya ~= model then
		eskiKopya:Destroy()
	end
	model.Name = ad
	model.Parent = hedef
	print(string.format("%s hazir -> %s.Assets.Monsters.%s  (%d parca)", ad, HEDEF_SERVIS.Name, ad, #tumParcalar + 1))
end

----------------------------------------------------------------------------
local bulunan = 0
local adaylar = {}
for _, s in ipairs(Selection:Get()) do
	if s:IsA("Model") then
		table.insert(adaylar, s)
	end
end
for _, c in ipairs(workspace:GetChildren()) do
	if c:IsA("Model") then
		table.insert(adaylar, c)
	end
end
local islenen = {}
for _, m in ipairs(adaylar) do
	local ad = m.Name
	if CANAVARLAR[ad] and not islenen[m] then
		islenen[m] = true
		bulunan = bulunan + 1
		kur(m, ad, CANAVARLAR[ad])
	end
end
if bulunan == 0 then
	warn("Workspace'te 'Fisilti', 'GeriDonen' veya 'Bakan' adli model bulunamadi. Once FBX'i Import 3D ile ice aktar.")
end
