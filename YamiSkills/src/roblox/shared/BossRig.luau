--[[
	BossRig - Kızıl Kemik İblisi modelini kurar (Humanoid + Motor6D iskelet).
	Parça/pivot verisi Blender'dan üretilen BossRigData'dan gelir, böylece Blender'daki
	animasyonlar bu iskelette birebir oynar.

	Assets.Meshes içinde "Boss_<Parça>" MeshPart'ları varsa (YamiBoss_Parts.fbx) onlar kullanılır,
	yoksa aynı iskelet basit parçalarla (top, bıçak, kemik, diken) kurulur.
]]
local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))
local Data = require(Shared:WaitForChild("BossRigData"))

local BossRig = {}

local function maxc(v: Vector3): number
	return math.max(v.X, v.Y, v.Z)
end

local function meshTemplate(name: string): MeshPart?
	if not Config.UseMeshes then
		return nil
	end
	local assets = Shared:FindFirstChild("Assets")
	local folder = assets and assets:FindFirstChild("Meshes")
	local found = folder and folder:FindFirstChild("Boss_" .. name, true)
	return if found and found:IsA("MeshPart") then found else nil
end

local function basePart(className: string?): BasePart
	local p = Instance.new(className or "Part") :: BasePart
	p.Anchored = false
	p.CanCollide = false
	p.CanTouch = false
	p.CanQuery = true
	p.Massless = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	return p
end

local function weldTo(main: BasePart, extra: BasePart)
	local w = Instance.new("Weld")
	w.Part0 = main
	w.Part1 = extra
	w.C0 = main.CFrame:ToObjectSpace(extra.CFrame)
	w.Parent = extra
end

-- Mesh yokken: aynı silueti veren basit parçalar. Dönen ana parça Motor6D'ye bağlanır.
local function fallbackPart(info, model: Model): BasePart
	local color = Data.Palette[info.Color]
	local material = (Enum.Material :: any)[info.Material] or Enum.Material.SmoothPlastic
	local center: Vector3 = info.Center
	local size: Vector3 = info.Size
	local pivot: Vector3 = info.Pivot
	local p = basePart()
	p.Color = color
	p.Material = material
	if info.Shape == "Ball" then
		p.Size = size
		p.CFrame = CFrame.new(center)
		local sm = Instance.new("SpecialMesh")
		sm.MeshType = Enum.MeshType.Sphere
		sm.Parent = p
	elseif info.Shape == "Blade" or info.Shape == "Bone" then
		local tip = center * 2 - pivot
		local len = (tip - pivot).Magnitude
		local mid = (pivot + tip) / 2
		if info.Shape == "Blade" then
			p.Size = Vector3.new(2.6, 0.45, len)
		else
			p.Size = Vector3.new(0.6, 0.6, len)
		end
		p.CFrame = CFrame.lookAt(mid, tip, Vector3.new(0, 0, -1))
		if info.Shape == "Blade" then -- kırmızı yarık çizgisi
			local stripe = basePart()
			stripe.Color = Config.Boss.Colors.Red
			stripe.Material = Enum.Material.Neon
			stripe.Size = Vector3.new(0.3, 0.5, len * 0.6)
			stripe.CFrame = p.CFrame * CFrame.new(0.6, 0.02, 0)
			stripe.CanQuery = false
			stripe.Parent = model
			weldTo(p, stripe)
		end
	elseif info.Shape == "Spikes" then -- taç: kırmızı/beyaz diken yelpazesi
		p.Size = Vector3.new(2.6, 2.2, 1.2)
		p.CFrame = CFrame.new(center - Vector3.new(0, size.Y * 0.3, 0))
		p.Color = Data.Palette[5]
		for i = 0, 10 do
			local ang = math.rad(-80 + 16 * i)
			local dir = Vector3.new(math.sin(ang), math.cos(ang), 0.25).Unit
			local len = 4.5 + 2.4 * math.cos(ang) ^ 2
			local s = basePart("WedgePart")
			s.Color = if i % 2 == 0 then Config.Boss.Colors.Red else Config.Boss.Colors.White
			s.Material = Enum.Material.SmoothPlastic
			s.Size = Vector3.new(0.35, len, if i % 2 == 0 then 1.6 else 1.1)
			local base = p.Position + dir * 1.2
			s.CFrame = CFrame.lookAt(base + dir * len / 2, base + dir * len / 2 + Vector3.new(0, 0, -1), dir)
			s.CanQuery = false
			s.Parent = model
			weldTo(p, s)
		end
	else
		p.Size = size
		p.CFrame = CFrame.new(center)
	end
	if info.Name == "Head" then -- tek siyah göz + kırmızı ağız
		local eye = basePart()
		eye.Shape = Enum.PartType.Ball
		eye.Size = Vector3.new(0.75, 0.75, 0.75)
		eye.Color = Color3.new(0, 0, 0)
		eye.CFrame = CFrame.new(center + Vector3.new(0, size.Y * 0.12, -size.Z * 0.42))
		eye.CanQuery = false
		eye.Parent = model
		weldTo(p, eye)
		local mouth = basePart()
		mouth.Size = Vector3.new(size.X * 0.55, 0.45, 0.3)
		mouth.Color = Config.Boss.Colors.Red
		mouth.CFrame = CFrame.new(center + Vector3.new(0, -size.Y * 0.22, -size.Z * 0.45))
		mouth.CanQuery = false
		mouth.Parent = model
		weldTo(p, mouth)
	end
	p.Parent = model
	return p
end

local function meshPart(info, template: MeshPart, model: Model): BasePart
	local m = template:Clone()
	m:ClearAllChildren()
	m.Name = info.Name
	m.Anchored = false
	m.CanCollide = false
	m.CanTouch = false
	m.CanQuery = true
	m.Massless = true
	m.Size = template.Size * (maxc(info.Size) / maxc(template.Size))
	m.CFrame = CFrame.new(info.Center)
	m.Parent = model
	return m
end

-- groundCFrame: bossun ayak tabanının konumu/yönü (boss bu CFrame'in LookVector'üne bakar)
function BossRig.Build(groundCFrame: CFrame): Model
	local cfg = Config.Boss
	local model = Instance.new("Model")
	model.Name = cfg.Name
	model:SetAttribute("YamiBoss", true)
	model:SetAttribute("KnockbackResist", cfg.KnockbackResist)

	local root = basePart()
	root.Name = "HumanoidRootPart"
	root.Size = Data.RootSize
	root.CFrame = CFrame.new(Data.RootCenter)
	root.Transparency = 1
	root.CanCollide = true
	root.Massless = false
	root.CustomPhysicalProperties = PhysicalProperties.new(2.5, 0.3, 0)
	root.Parent = model
	model.PrimaryPart = root

	local parts: { [string]: BasePart } = { HumanoidRootPart = root }
	for _, info in ipairs(Data.Parts) do
		local template = meshTemplate(info.Name)
		local p = if template then meshPart(info, template, model) else fallbackPart(info, model)
		p.Name = info.Name
		parts[info.Name] = p
	end
	-- Motor6D'ler: eklem çerçevesi pivotta ve model eksenine hizalı (Blender export'u ile aynı)
	for _, info in ipairs(Data.Parts) do
		local p0 = parts[info.Parent]
		local p1 = parts[info.Name]
		local pivot = CFrame.new(info.Pivot)
		local m = Instance.new("Motor6D")
		m.Name = info.Name
		m.Part0 = p0
		m.Part1 = p1
		m.C0 = p0.CFrame:Inverse() * pivot
		m.C1 = p1.CFrame:Inverse() * pivot
		m.Parent = p1
	end

	local hum = Instance.new("Humanoid")
	hum.RigType = Enum.HumanoidRigType.R15
	hum.AutomaticScalingEnabled = false
	hum.RequiresNeck = false
	hum.BreakJointsOnDeath = false
	hum.HipHeight = Data.HipHeight
	hum.MaxHealth = cfg.MaxHealth
	hum.Health = cfg.MaxHealth
	hum.WalkSpeed = cfg.WalkSpeed
	hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	hum.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	Instance.new("Animator").Parent = hum
	hum.Parent = model

	-- yapı zemin orijininde kuruldu; modelin pivotu kök parça (RootCenter yüksekliğinde)
	model:PivotTo(groundCFrame * CFrame.new(Data.RootCenter))
	return model
end

return BossRig
