--[[
	KatanaRig - Yami'nin katanası ve kılıfı (saya).
	Sunucu karakter doğunca Build() ile modeli kurar ve kalçaya (kılıfa) kaynaklar.
	Kuşanınca sağ ele, bırakınca kılıfa geçer. Client da aynı fonksiyonla kendi karakterinde
	anında (gecikmesiz) değiştirir; sunucu sonra aynı değeri gönderir.

	Katana yerel ekseni: kabza merkezi = orijin, namlu -Z yönünde, keskin ağız -Y yönünde.
	Assets.Meshes içinde "Katana" / "KatanaSaya" MeshPart'ları varsa onlar kullanılır.
]]
local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))

local KatanaRig = {}

local GRIP_IN_HAND = CFrame.new(0, -0.1, 0)
local SHEATHED_OFFSET = CFrame.new(0, 0, 0.55) -- kabza kılıf ağzının arkasında

local function sayaFrame(lowerTorso: BasePart): CFrame
	local s = lowerTorso.Size
	return CFrame.fromMatrix(
		Vector3.new(-(s.X / 2 + 0.08), 0.05, -s.Z * 0.42),
		Vector3.new(0.9912, 0, 0.1322),
		Vector3.new(0.0555, -0.9076, -0.4161),
		Vector3.new(0.12, 0.4198, -0.8996)
	)
end

local function newPart(
	parent: Instance,
	name: string,
	size: Vector3,
	cf: CFrame,
	color: Color3,
	material: Enum.Material,
	className: string?
): BasePart
	local p = Instance.new(className or "Part") :: BasePart
	p.Name = name
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
	p.Anchored = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
	return p
end

-- C0/C1'li Weld: modelin nerede kurulduğundan bağımsız, her zaman aynı yerleşim
local function weldAll(model: Model, root: BasePart)
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and d ~= root then
			local w = Instance.new("Weld")
			w.Name = "YamiPartWeld"
			w.Part0 = root
			w.Part1 = d
			w.C0 = root.CFrame:ToObjectSpace(d.CFrame)
			w.Parent = d
		end
	end
end

local function meshTemplate(name: string): MeshPart?
	if not Config.UseMeshes then
		return nil
	end
	local assets = Shared:FindFirstChild("Assets")
	local folder = assets and assets:FindFirstChild("Meshes")
	local found = folder and folder:FindFirstChild(name, true)
	return if found and found:IsA("MeshPart") then found else nil
end

local function addMesh(model: Model, name: string, designMax: number, at: CFrame): MeshPart?
	local template = meshTemplate(name)
	if template == nil then
		return nil
	end
	local m = template:Clone()
	m:ClearAllChildren()
	m.Name = name .. "Mesh"
	m.Anchored = false
	m.CanCollide = false
	m.CanQuery = false
	m.CanTouch = false
	m.Massless = true
	local maxT = math.max(template.Size.X, template.Size.Y, template.Size.Z)
	m.Size = template.Size * (designMax / maxT)
	local r = Config.MeshRotation[name] or Vector3.zero
	m.CFrame = at * CFrame.Angles(math.rad(r.X), math.rad(r.Y), math.rad(r.Z))
	m.Parent = model
	return m
end

function KatanaRig.BuildKatana(): Model
	local model = Instance.new("Model")
	model.Name = "YamiKatana"
	local o = CFrame.new()
	local root =
		newPart(model, "KatanaRoot", Vector3.new(0.2, 0.2, 0.2), o, Color3.new(0, 0, 0), Enum.Material.SmoothPlastic)
	root.Transparency = 1
	model.PrimaryPart = root

	local black = Color3.fromRGB(14, 14, 16)
	local iron = Color3.fromRGB(38, 38, 42)
	local gold = Color3.fromRGB(196, 152, 58)
	local steel = Color3.fromRGB(196, 200, 210)
	local visual = {}
	table.insert(
		visual,
		newPart(model, "Handle", Vector3.new(0.19, 0.25, 1.22), o * CFrame.new(0, 0, 0.13), black, Enum.Material.Fabric)
	)
	for i, z in ipairs({ -0.35, -0.12, 0.11, 0.34, 0.57 }) do
		for _, x in ipairs({ -0.097, 0.097 }) do
			table.insert(
				visual,
				newPart(
					model,
					"Wrap" .. i,
					Vector3.new(0.02, 0.085, 0.085),
					o * CFrame.new(x, 0, z) * CFrame.Angles(math.rad(45), 0, 0),
					Color3.fromRGB(225, 222, 210),
					Enum.Material.SmoothPlastic
				)
			)
		end
	end
	table.insert(
		visual,
		newPart(model, "Pommel", Vector3.new(0.21, 0.27, 0.07), o * CFrame.new(0, 0, 0.775), iron, Enum.Material.Metal)
	)
	table.insert(
		visual,
		newPart(model, "Fuchi", Vector3.new(0.21, 0.27, 0.06), o * CFrame.new(0, 0, -0.47), iron, Enum.Material.Metal)
	)
	local guard = newPart(
		model,
		"Guard",
		Vector3.new(0.06, 0.6, 0.6),
		o * CFrame.new(0, 0, -0.53) * CFrame.Angles(0, math.rad(90), 0),
		Color3.fromRGB(24, 24, 27),
		Enum.Material.Metal
	);
	(guard :: Part).Shape = Enum.PartType.Cylinder
	table.insert(visual, guard)
	table.insert(
		visual,
		newPart(model, "Habaki", Vector3.new(0.1, 0.25, 0.13), o * CFrame.new(0, 0, -0.625), gold, Enum.Material.Metal)
	)
	local blade =
		newPart(model, "Blade", Vector3.new(0.05, 0.2, 3.0), o * CFrame.new(0, 0.01, -2.19), steel, Enum.Material.Metal)
	blade.Reflectance = 0.15
	table.insert(visual, blade)
	table.insert(
		visual,
		newPart(
			model,
			"Edge",
			Vector3.new(0.03, 0.045, 3.0),
			o * CFrame.new(0, -0.08, -2.19),
			Color3.fromRGB(236, 238, 244),
			Enum.Material.SmoothPlastic
		)
	)
	table.insert(
		visual,
		newPart(
			model,
			"Tip",
			Vector3.new(0.05, 0.2, 0.42),
			o * CFrame.new(0, 0.01, -3.9) * CFrame.Angles(0, 0, math.pi),
			steel,
			Enum.Material.Metal,
			"WedgePart"
		)
	)

	-- iz (trail) için bağlantı noktaları - namlu boyunca
	local base = Instance.new("Attachment")
	base.Name = "TrailBase"
	base.Position = Vector3.new(0, 0, 1.3)
	base.Parent = blade
	local tip = Instance.new("Attachment")
	tip.Name = "TrailTip"
	tip.Position = Vector3.new(0, 0, -1.85)
	tip.Parent = blade
	local trail = Instance.new("Trail")
	trail.Name = "YamiTrail"
	trail.Attachment0 = base
	trail.Attachment1 = tip
	trail.Color = ColorSequence.new(Config.Theme.Core)
	trail.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.05), NumberSequenceKeypoint.new(1, 1) })
	trail.WidthScale = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(1, 0.35) })
	trail.Lifetime = 0.17
	trail.LightEmission = 0
	trail.LightInfluence = 0
	trail.MinLength = 0.05
	trail.FaceCamera = false
	trail.Enabled = false
	trail.Parent = blade

	if addMesh(model, "Katana", 7.96, o) then
		for _, p in ipairs(visual) do
			p.Transparency = 1
		end
	end
	weldAll(model, root)
	return model
end

function KatanaRig.BuildSaya(): Model
	local model = Instance.new("Model")
	model.Name = "YamiSaya"
	local o = CFrame.new()
	local root =
		newPart(model, "SayaRoot", Vector3.new(0.2, 0.2, 0.2), o, Color3.new(0, 0, 0), Enum.Material.SmoothPlastic)
	root.Transparency = 1
	model.PrimaryPart = root
	local visual = {}
	local body = newPart(
		model,
		"SayaBody",
		Vector3.new(0.17, 0.3, 3.5),
		o * CFrame.new(0, 0, -1.83),
		Color3.fromRGB(10, 10, 12),
		Enum.Material.SmoothPlastic
	)
	body.Reflectance = 0.06
	table.insert(visual, body)
	table.insert(
		visual,
		newPart(
			model,
			"Koiguchi",
			Vector3.new(0.2, 0.33, 0.1),
			o * CFrame.new(0, 0, -0.04),
			Color3.fromRGB(38, 38, 42),
			Enum.Material.Metal
		)
	)
	table.insert(
		visual,
		newPart(
			model,
			"Kojiri",
			Vector3.new(0.18, 0.31, 0.1),
			o * CFrame.new(0, 0, -3.62),
			Color3.fromRGB(38, 38, 42),
			Enum.Material.Metal
		)
	)
	if addMesh(model, "KatanaSaya", 7.4, o) then
		for _, p in ipairs(visual) do
			p.Transparency = 1
		end
	end
	weldAll(model, root)
	return model
end

local function gripWeld(char: Model): Weld?
	local k = char:FindFirstChild("YamiKatana")
	local root = k and k:FindFirstChild("KatanaRoot")
	local w = root and root:FindFirstChild("YamiGripWeld")
	return if w and w:IsA("Weld") then w else nil
end

function KatanaRig.ToHand(char: Model): boolean
	local w = gripWeld(char)
	local hand = char:FindFirstChild("RightHand")
	if w == nil or hand == nil or not hand:IsA("BasePart") then
		return false
	end
	w.Part0 = hand
	w.C0 = GRIP_IN_HAND
	return true
end

function KatanaRig.ToHip(char: Model): boolean
	local w = gripWeld(char)
	local lt = char:FindFirstChild("LowerTorso")
	if w == nil or lt == nil or not lt:IsA("BasePart") then
		return false
	end
	w.Part0 = lt
	w.C0 = sayaFrame(lt) * SHEATHED_OFFSET
	return true
end

-- Sunucu: karakter için katana + saya kur (kılıfta)
function KatanaRig.Setup(char: Model)
	local lt = char:WaitForChild("LowerTorso", 10)
	local hand = char:WaitForChild("RightHand", 10)
	if lt == nil or hand == nil or not lt:IsA("BasePart") then
		warn("[YamiSkills] R15 karakter gerekli (LowerTorso/RightHand bulunamadı)")
		return
	end
	for _, name in ipairs({ "YamiKatana", "YamiSaya" }) do
		local old = char:FindFirstChild(name)
		if old then
			old:Destroy()
		end
	end
	local saya = KatanaRig.BuildSaya()
	local sayaRoot = saya.PrimaryPart :: BasePart
	local sw = Instance.new("Weld")
	sw.Name = "YamiSayaWeld"
	sw.Part0 = lt
	sw.Part1 = sayaRoot
	sw.C0 = sayaFrame(lt)
	sw.Parent = sayaRoot
	saya.Parent = char

	local katana = KatanaRig.BuildKatana()
	local root = katana.PrimaryPart :: BasePart
	local w = Instance.new("Weld")
	w.Name = "YamiGripWeld"
	w.Part0 = lt
	w.Part1 = root
	w.C0 = sayaFrame(lt) * SHEATHED_OFFSET
	w.Parent = root
	katana.Parent = char
end

return KatanaRig
