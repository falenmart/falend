--[[
	VFX (client) - siyah büyü efekt araç kutusu.
	Blender meshleri (Assets.Meshes içindeyse) kullanılır; yoksa aynı efekt Part'larla çizilir.

	Crescent   : hilal kılıç izi (M1, Kara Hilal)
	Rift       : boyut yarığı (Boyut Kesiği)
	Shockwave  : yere yayılan şok halkası
	Shards     : uzayın çatlaması (kıymıklar)
	ImpactStar : darbe yıldızı
	Afterimage : siyah gölge-iz (Ölüm Saplaması)
	Burst/Emitter : parçacık hazır ayarları (Smoke, Sparks, Embers, Ring, Wisps, Dust, Ink)
]]
local Debris = game:GetService("Debris")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))

local VFX = {}

local BLACK = Config.Theme.Core
local ACCENT = Config.Theme.Accent

-- -------------------------------------------------------------- temel yardımcılar

function VFX.Folder(): Folder
	local f = workspace:FindFirstChild("YamiFX")
	if f == nil then
		f = Instance.new("Folder")
		f.Name = "YamiFX"
		f.Parent = workspace
	end
	return f :: Folder
end

function VFX.Part(props: { [string]: any }?): BasePart
	props = props or {}
	local p = Instance.new((props :: any).ClassName or "Part") :: BasePart
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Massless = true
	p.Material = Enum.Material.Neon
	p.Color = BLACK
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	for k, v in pairs(props :: any) do
		if k ~= "ClassName" and k ~= "Parent" then
			(p :: any)[k] = v
		end
	end
	p.Parent = (props :: any).Parent or VFX.Folder()
	return p
end

function VFX.Tween(
	obj: Instance,
	t: number,
	goal: { [string]: any },
	style: Enum.EasingStyle?,
	dir: Enum.EasingDirection?
)
	local tw = TweenService:Create(
		obj,
		TweenInfo.new(t, style or Enum.EasingStyle.Quad, dir or Enum.EasingDirection.Out),
		goal
	)
	tw:Play()
	return tw
end

function VFX.FadeDestroy(obj: Instance, t: number, delayTime: number?)
	task.delay(delayTime or 0, function()
		if obj.Parent == nil then
			return
		end
		local goal: { [string]: any } = {}
		if obj:IsA("BasePart") or obj:IsA("Decal") then
			goal.Transparency = 1
		end
		if next(goal) then
			VFX.Tween(obj, t, goal)
		end
		Debris:AddItem(obj, t + 0.05)
	end)
end

-- Her karede update(alpha) çağırır (0 -> 1). Dönen fonksiyon iptal eder.
function VFX.Animate(duration: number, update: (number) -> ()): () -> ()
	local start = os.clock()
	local conn: RBXScriptConnection
	conn = RunService.RenderStepped:Connect(function()
		local a = math.clamp((os.clock() - start) / math.max(duration, 1e-3), 0, 1)
		local ok, err = pcall(update, a)
		if a >= 1 or not ok then
			conn:Disconnect()
			if not ok then
				warn("[YamiSkills] VFX:", err)
			end
		end
	end)
	task.spawn(update, 0)
	return function()
		if conn.Connected then
			conn:Disconnect()
		end
	end
end

local function outQuint(a: number): number
	return 1 - (1 - a) ^ 5
end
local function outCubic(a: number): number
	return 1 - (1 - a) ^ 3
end
VFX.outQuint = outQuint
VFX.outCubic = outCubic

-- -------------------------------------------------------------------- meshler

local DESIGN: { [string]: Vector3 } = {
	SlashArc = Vector3.new(10.21, 0.128, 10.656),
	DimensionRift = Vector3.new(100, 5.935, 0.381),
	ShockRing = Vector3.new(2, 0.18, 2),
	Swirl = Vector3.new(2.857, 2.285, 2.514),
	Cocoon = Vector3.new(2.334, 2.151, 2.396),
	Shard = Vector3.new(0.12, 0.04, 1),
	ImpactStar = Vector3.new(1.736, 1.843, 0.05),
	Katana = Vector3.new(0.54, 0.62, 7.96),
	KatanaSaya = Vector3.new(0.196, 0.454, 7.4),
	Rock1 = Vector3.new(1.447, 1.428, 2.056),
	Rock2 = Vector3.new(2.575, 1.474, 1.642),
	Rock3 = Vector3.new(1.505, 1.263, 1.647),
}
VFX.DESIGN = DESIGN

local meshCache: { [string]: { part: MeshPart?, checked: number } } = {}

function VFX.MeshTemplate(name: string): MeshPart?
	if not Config.UseMeshes then
		return nil
	end
	local c = meshCache[name]
	if c and (c.part ~= nil or os.clock() - c.checked < 5) then
		return c.part
	end
	local assets = Shared:FindFirstChild("Assets")
	local folder = assets and assets:FindFirstChild("Meshes")
	local found = folder and folder:FindFirstChild(name, true)
	local part = if found and found:IsA("MeshPart") then found else nil
	meshCache[name] = { part = part, checked = os.clock() }
	return part
end

function VFX.MeshOffset(name: string): CFrame
	local r = Config.MeshRotation[name] or Vector3.zero
	return CFrame.Angles(math.rad(r.X), math.rad(r.Y), math.rad(r.Z))
end

local function maxc(v: Vector3): number
	return math.max(v.X, v.Y, v.Z)
end

-- Blender meshinin kopyası. scale = Blender'daki tasarım ölçüsüne göre çarpan (1 = tasarım).
function VFX.Mesh(name: string, scale: number?, props: { [string]: any }?): MeshPart?
	local template = VFX.MeshTemplate(name)
	if template == nil then
		return nil
	end
	local m = template:Clone()
	m:ClearAllChildren()
	m.Anchored = true
	m.CanCollide = false
	m.CanQuery = false
	m.CanTouch = false
	m.CastShadow = false
	m.Massless = true
	local design = DESIGN[name] or template.Size
	m.Size = template.Size * ((scale or 1) * maxc(design) / maxc(template.Size))
	if props then
		for k, v in pairs(props) do
			(m :: any)[k] = v
		end
	end
	m.Parent = VFX.Folder()
	return m
end

-- --------------------------------------------------------------- parçacıklar

local function kp(t: number, v: number, e: number?)
	return NumberSequenceKeypoint.new(t, v, e or 0)
end
local function ns(points: { { number } }): NumberSequence
	local list = {}
	for _, p in ipairs(points) do
		table.insert(list, kp(p[1], p[2], p[3]))
	end
	return NumberSequence.new(list)
end
VFX.ns = ns

local function tex(preferred: string, fallback: string): string
	local t = Config.Textures[preferred]
	if type(t) == "string" and t ~= "" then
		return t
	end
	return Config.Textures[fallback]
end

local PRESETS: { [string]: () -> { [string]: any } } = {
	Smoke = function()
		return {
			Texture = tex("InkSmoke", "Smoke"),
			Size = ns({ { 0, 1.6 }, { 1, 5.5 } }),
			Transparency = ns({ { 0, 0.15 }, { 0.55, 0.4 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.6, 1.2),
			Speed = NumberRange.new(4, 11),
			SpreadAngle = Vector2.new(180, 180),
			Drag = 4,
			Rotation = NumberRange.new(0, 360),
			RotSpeed = NumberRange.new(-90, 90),
			Acceleration = Vector3.new(0, 3, 0),
		}
	end,
	Ink = function() -- yoğun siyah mürekkep bulutu
		return {
			Texture = tex("InkSmoke", "Smoke"),
			Size = ns({ { 0, 3 }, { 0.3, 6 }, { 1, 9 } }),
			Transparency = ns({ { 0, 0.05 }, { 0.6, 0.3 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.8, 1.5),
			Speed = NumberRange.new(10, 26),
			SpreadAngle = Vector2.new(180, 180),
			Drag = 5,
			Rotation = NumberRange.new(0, 360),
			RotSpeed = NumberRange.new(-60, 60),
		}
	end,
	Sparks = function() -- siyah çizgi kıvılcımlar
		return {
			Texture = tex("Streak", "Spark"),
			Orientation = Enum.ParticleOrientation.VelocityParallel,
			Squash = ns({ { 0, 1.6 }, { 1, 2.4 } }),
			Size = ns({ { 0, 1.1 }, { 1, 0 } }),
			Transparency = ns({ { 0, 0 }, { 1, 0.4 } }),
			Lifetime = NumberRange.new(0.18, 0.4),
			Speed = NumberRange.new(45, 90),
			SpreadAngle = Vector2.new(180, 180),
			Drag = 7,
		}
	end,
	Embers = function() -- yukarı süzülen siyah zerreler
		return {
			Texture = Config.Textures.Square,
			Size = ns({ { 0, 0.32 }, { 1, 0 } }),
			Transparency = ns({ { 0, 0 }, { 1, 0.6 } }),
			Lifetime = NumberRange.new(0.7, 1.4),
			Speed = NumberRange.new(2, 6),
			SpreadAngle = Vector2.new(180, 180),
			Acceleration = Vector3.new(0, 9, 0),
			Drag = 1.5,
			Rotation = NumberRange.new(0, 360),
			RotSpeed = NumberRange.new(-200, 200),
		}
	end,
	Wisps = function() -- yükselen karanlık alev / aura
		return {
			Texture = tex("InkSmoke", "Smoke"),
			Size = ns({ { 0, 0.9 }, { 0.4, 1.7 }, { 1, 0.2 } }),
			Transparency = ns({ { 0, 0.4 }, { 0.3, 0.1 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.45, 0.8),
			Speed = NumberRange.new(1, 3),
			SpreadAngle = Vector2.new(25, 25),
			Acceleration = Vector3.new(0, 7, 0),
			Rotation = NumberRange.new(0, 360),
			RotSpeed = NumberRange.new(-120, 120),
			Rate = 40,
		}
	end,
	Ring = function() -- düz şok halkası (parçacık)
		return {
			Texture = Config.Textures.Shockwave,
			Orientation = Enum.ParticleOrientation.VelocityPerpendicular,
			Size = ns({ { 0, 2 }, { 1, 30 } }),
			Transparency = ns({ { 0, 0.05 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.45, 0.45),
			Speed = NumberRange.new(0.01, 0.01),
			SpreadAngle = Vector2.new(0, 0),
			EmissionDirection = Enum.NormalId.Top,
		}
	end,
	Dust = function() -- yer tozu (rengi zeminden gelir)
		return {
			Texture = Config.Textures.Smoke,
			Size = ns({ { 0, 2.5 }, { 1, 7 } }),
			Transparency = ns({ { 0, 0.35 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.9, 1.6),
			Speed = NumberRange.new(8, 22),
			SpreadAngle = Vector2.new(90, 10),
			Drag = 3,
			Rotation = NumberRange.new(0, 360),
			RotSpeed = NumberRange.new(-50, 50),
			Acceleration = Vector3.new(0, -2, 0),
			LightInfluence = 1,
		}
	end,
	Implode = function() -- dışarıdan içeri toplanan karanlık
		return {
			Texture = tex("InkSmoke", "Smoke"),
			Size = ns({ { 0, 2.2 }, { 1, 0.2 } }),
			Transparency = ns({ { 0, 1 }, { 0.25, 0.25 }, { 1, 0 } }),
			Lifetime = NumberRange.new(0.35, 0.5),
			Speed = NumberRange.new(20, 26),
			Shape = Enum.ParticleEmitterShape.Sphere,
			ShapeStyle = Enum.ParticleEmitterShapeStyle.Surface,
			ShapeInOut = Enum.ParticleEmitterShapeInOut.Inward,
			Rotation = NumberRange.new(0, 360),
			Rate = 60,
		}
	end,
}

function VFX.Emitter(parent: Instance, preset: string, overrides: { [string]: any }?): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.Name = "Yami" .. preset
	e.Color = ColorSequence.new(BLACK)
	e.LightEmission = 0
	e.LightInfluence = 0
	e.Rate = 0
	e.Enabled = true
	local props = PRESETS[preset]()
	if overrides then
		for k, v in pairs(overrides) do
			props[k] = v
		end
	end
	for k, v in pairs(props) do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

function VFX.Attachment(cf: CFrame | Vector3): Attachment
	local a = Instance.new("Attachment")
	a.Name = "YamiFXPoint"
	a.Parent = workspace.Terrain
	if typeof(cf) == "Vector3" then
		a.WorldPosition = cf
	else
		a.WorldCFrame = cf
	end
	return a
end

-- Tek seferlik parçacık patlaması
function VFX.Burst(at: CFrame | Vector3, preset: string, count: number, overrides: { [string]: any }?)
	local a = VFX.Attachment(at)
	local e = VFX.Emitter(a, preset, overrides)
	e.Enabled = false
	e:Emit(count)
	Debris:AddItem(a, e.Lifetime.Max + 0.3)
	return e
end

-- ------------------------------------------------------------- hilal (kesik izi)

--[[
	cf      : hilal çemberinin merkezi; hilal cf'in XZ düzleminde, cf.LookVector yönüne doğru şişer
	opts    : Radius (5), Roll (derece, kesik düzlemi), Sweep (derece), Duration, Grow, Width (kalınlık çarpanı)
	Hilalin "başı" (kalın ucu) +X tarafındadır; Roll = 180 ile ters çevrilir.
]]
function VFX.Crescent(cf: CFrame, opts: { [string]: any }?)
	opts = opts or {}
	local o = opts :: any
	local radius = o.Radius or 5
	local roll = math.rad(o.Roll or 0)
	local sweep = math.rad(o.Sweep or 45)
	local dur = o.Duration or 0.3
	local grow = o.Grow or 1.12
	local base = cf * CFrame.Angles(0, 0, roll)
	local color: Color3 = o.Color or BLACK
	local mesh = VFX.Mesh("SlashArc", radius / 5)
	if mesh then
		local off = VFX.MeshOffset("SlashArc")
		local size0 = mesh.Size
		local t0 = o.Transparency or 0.01
		mesh.Color = color
		if o.Color then -- renkli kesik: siyah dokuyu kaldır
			mesh.TextureID = ""
			t0 = math.max(t0, 0.15)
		end
		VFX.Animate(dur, function(a)
			local e = outCubic(a)
			mesh.Size = size0 * (1 + (grow - 1) * e)
			mesh.CFrame = base * CFrame.Angles(0, sweep * (0.5 - e), 0) * off
			mesh.Transparency = t0 + (1 - t0) * a ^ 1.6
			if a >= 1 then
				mesh:Destroy()
			end
		end)
		return
	end
	-- Fallback: hilali ince siyah parçalardan çiz
	local segs = 20
	local span = math.rad(200)
	local W = 1.5 * radius / 5 * (o.Width or 1)
	local parts = {}
	for i = 1, segs do
		local u0, u1 = (i - 1) / segs, i / segs
		local um = (u0 + u1) / 2
		local th = -span / 2 + um * span
		local t = W * math.sin(math.pi * um ^ 0.85) ^ 0.75
		if t > 0.03 then
			local rmid = radius - 0.28 * t
			local chord = 2 * rmid * math.sin(span / segs / 2) * 1.08
			local local_cf = CFrame.new(math.sin(th) * rmid, 0, -math.cos(th) * rmid) * CFrame.Angles(0, -th, 0)
			local p = VFX.Part({
				Size = Vector3.new(chord, 0.14, t),
				Transparency = 0.04 + 0.6 * (1 - um) ^ 2,
				Color = color,
			})
			table.insert(parts, { part = p, cf = local_cf, base = p.Transparency, size = p.Size })
		end
	end
	VFX.Animate(dur, function(a)
		local e = outCubic(a)
		local s = 1 + (grow - 1) * e
		local frame = base * CFrame.Angles(0, sweep * (0.5 - e), 0)
		for _, seg in ipairs(parts) do
			local lc = seg.cf
			seg.part.CFrame = frame * CFrame.new(lc.Position * s) * lc.Rotation
			seg.part.Size = seg.size * Vector3.new(s, 1, 1)
			seg.part.Transparency = seg.base + (1 - seg.base) * a ^ 1.6
		end
		if a >= 1 then
			for _, seg in ipairs(parts) do
				seg.part:Destroy()
			end
		end
	end)
end

-- Uçan hilal (Kara Hilal mermisi): kendi konumunu cf ile her kare günceller
function VFX.CrescentProjectile(
	radius: number
): { Set: (self: any, cf: CFrame, alpha: number) -> (), Destroy: (self: any) -> () }
	local obj = {}
	local mesh = VFX.Mesh("SlashArc", radius / 5)
	local parts = {}
	if mesh then
		mesh.Color = BLACK
		mesh.Transparency = 0.01
	else
		local segs, span, W = 22, math.rad(200), 1.5 * radius / 5
		for i = 1, segs do
			local um = (i - 0.5) / segs
			local th = -span / 2 + um * span
			local t = W * math.sin(math.pi * um) ^ 0.8 -- simetrik (uçarken)
			if t > 0.03 then
				local rmid = radius - 0.28 * t
				local chord = 2 * rmid * math.sin(span / segs / 2) * 1.08
				local lc = CFrame.new(math.sin(th) * rmid, 0, -math.cos(th) * rmid) * CFrame.Angles(0, -th, 0)
				local p = VFX.Part({ Size = Vector3.new(chord, 0.3, t) })
				table.insert(parts, { part = p, cf = lc })
			end
		end
	end
	local off = VFX.MeshOffset("SlashArc")
	function obj.Set(_, cf: CFrame, transparency: number)
		if mesh then
			mesh.CFrame = cf * off
			mesh.Transparency = math.max(0.01, transparency)
		else
			for _, seg in ipairs(parts) do
				seg.part.CFrame = cf * seg.cf
				seg.part.Transparency = transparency
			end
		end
	end
	function obj.Destroy()
		if mesh then
			mesh:Destroy()
		end
		for _, seg in ipairs(parts) do
			seg.part:Destroy()
		end
	end
	return obj :: any
end

-- ---------------------------------------------------------------- boyut yarığı

local function outline(adornee: Instance, transparency: number?): Highlight?
	if Config.Theme.OutlineTransparency >= 1 then
		return nil
	end
	local h = Instance.new("Highlight")
	h.Name = "YamiOutline"
	h.Adornee = adornee
	h.FillColor = BLACK
	h.FillTransparency = 1
	h.OutlineColor = ACCENT
	h.OutlineTransparency = transparency or Config.Theme.OutlineTransparency
	h.DepthMode = Enum.HighlightDepthMode.Occluded
	h.Parent = adornee
	return h
end
VFX.Outline = outline

--[[
	Rift(cf, opts) -> handle:Close()
	cf: yarığın merkezi. Uzun eksen = cf.RightVector, açıklık = cf.UpVector, yüz = cf.LookVector.
	opts: Length, Open (açıklık yüksekliği), OpenTime, Pulse
]]
function VFX.Rift(cf: CFrame, opts: { [string]: any }?)
	opts = opts or {}
	local o = opts :: any
	local L = o.Length or 200
	local H = o.Open or 7
	local openTime = o.OpenTime or 0.07
	local holder = Instance.new("Model")
	holder.Name = "YamiRift"
	holder.Parent = VFX.Folder()
	local body: BasePart
	local setOpen: (number) -> ()
	local mesh = VFX.Mesh("DimensionRift", L / 100, { Parent = holder })
	if mesh then
		local off = VFX.MeshOffset("DimensionRift")
		local s0 = mesh.Size
		local designH = DESIGN.DimensionRift.Y * (L / 100)
		mesh.Color = BLACK
		mesh.Material = Enum.Material.Neon
		mesh.CFrame = cf * off
		body = mesh
		setOpen = function(h)
			local k = math.max(h / designH, 0.002)
			mesh.Size = Vector3.new(s0.X, s0.Y * k, s0.Z * math.clamp(k, 0.3, 1))
		end
	else
		local p = VFX.Part({ Size = Vector3.new(L, 0.05, 0.6), CFrame = cf, Parent = holder })
		local sm = Instance.new("SpecialMesh")
		sm.MeshType = Enum.MeshType.Sphere
		sm.Parent = p
		body = p
		setOpen = function(h)
			p.Size = Vector3.new(L, math.max(h, 0.02), 0.6)
		end
	end
	setOpen(0)
	outline(holder, 0)
	-- dikenli kenarlar: 45 derece döndürülmüş kareler (yarığın kenarından üçgen olarak taşar)
	local teeth = {}
	local rng = Random.new()
	for i = 1, 28 do
		local x = rng:NextNumber(-0.44, 0.44) * L
		local side = if i % 2 == 0 then 1 else -1
		local len = rng:NextNumber(1.2, 4.2) * (1 - math.abs(x) / (L * 0.5)) + 0.3
		local t = VFX.Part({ Size = Vector3.new(len * 0.55, len * 0.55, 0.2), Transparency = 1, Parent = holder })
		table.insert(teeth, { part = t, x = x, side = side, len = len })
	end
	local function placeTeeth(h: number, alpha: number)
		for _, tt in ipairs(teeth) do
			local k = math.max(1 - (2 * tt.x / L) ^ 2, 0)
			local y = tt.side * h * 0.5 * k
			tt.part.CFrame = cf * CFrame.new(tt.x, y, 0) * CFrame.Angles(0, 0, math.rad(45))
			tt.part.Transparency = if h < 0.05 then 1 else 1 - alpha
		end
	end
	local alive = true
	local current = 0
	VFX.Animate(openTime, function(a)
		current = H * (1.18 * outQuint(a))
		setOpen(current)
		placeTeeth(current, a)
	end)
	task.delay(openTime, function()
		VFX.Animate(0.12, function(a)
			current = H * (1.18 - 0.18 * a)
			setOpen(current)
			placeTeeth(current, 1)
		end)
	end)
	-- yavaş nabız
	task.delay(openTime + 0.12, function()
		local t0 = os.clock()
		while alive and holder.Parent do
			local k = 1 + 0.06 * math.sin((os.clock() - t0) * 9)
			current = H * k
			setOpen(current)
			placeTeeth(current, 1)
			RunService.RenderStepped:Wait()
		end
	end)
	local handle = { Model = holder, Body = body }
	function handle.Close(_, t: number?)
		if not alive then
			return
		end
		alive = false
		local closeT = t or 0.22
		local h0 = current
		-- kapanırken ince beyaz dikiş
		local seam =
			VFX.Part({ Size = Vector3.new(L * 0.98, 0.12, 0.12), CFrame = cf, Color = ACCENT, Transparency = 1 })
		VFX.Animate(closeT, function(a)
			local e = a * a
			setOpen(h0 * (1 - e))
			placeTeeth(h0 * (1 - e), 1 - a)
			seam.Transparency = 1 - math.sin(math.pi * a) * 0.85
			if a >= 1 then
				holder:Destroy()
				VFX.FadeDestroy(seam, 0.15)
			end
		end)
	end
	return handle
end

-- ---------------------------------------------------------------- şok halkası

function VFX.Shockwave(cf: CFrame | Vector3, opts: { [string]: any }?)
	opts = opts or {}
	local o = opts :: any
	local frame = if typeof(cf) == "Vector3" then CFrame.new(cf) else cf
	local radius = o.Radius or 18
	local dur = o.Duration or 0.45
	local mesh = VFX.Mesh("ShockRing", 1)
	if mesh then
		local off = VFX.MeshOffset("ShockRing")
		local s0 = mesh.Size / math.max(mesh.Size.X, 1e-3)
		mesh.Color = o.Color or BLACK
		if o.Color then
			mesh.TextureID = ""
		end
		local thick = o.Thickness or 1
		VFX.Animate(dur, function(a)
			local e = outQuint(a)
			local r = 0.8 + (radius - 0.8) * e
			mesh.Size = Vector3.new(s0.X * r * 2, s0.Y * r * 2 * 0.25 * thick, s0.Z * r * 2)
			mesh.CFrame = frame * off
			mesh.Transparency = 0.02 + 0.98 * a ^ 1.4
			if a >= 1 then
				mesh:Destroy()
			end
		end)
	else
		VFX.Burst(frame, "Ring", 1, {
			Color = ColorSequence.new(o.Color or BLACK),
			Size = ns({ { 0, 1.5 }, { 1, radius * 2 } }),
			Lifetime = NumberRange.new(dur, dur),
		})
	end
end

-- ------------------------------------------------------------------ kıymıklar

-- Uzayın çatlaması: cf etrafında, cf'in XY düzleminde dışa doğru kıymıklar
function VFX.Shards(cf: CFrame, opts: { [string]: any }?)
	opts = opts or {}
	local o = opts :: any
	local count = o.Count or 12
	local spreadX = o.SpreadX or 0
	local len0, len1 = o.MinLength or 3, o.MaxLength or 9
	local dur = o.Duration or 0.6
	local rng = Random.new(o.Seed or os.clock() * 1000)
	for _ = 1, count do
		local x = rng:NextNumber(-0.5, 0.5) * spreadX
		local ang = rng:NextNumber(0, math.pi * 2)
		if o.Vertical then -- yarıktan yukarı/aşağı fışkıran
			ang = (if rng:NextNumber() < 0.5 then math.pi / 2 else -math.pi / 2) + rng:NextNumber(-0.6, 0.6)
		end
		local len = rng:NextNumber(len0, len1)
		local dir = Vector3.new(math.cos(ang), math.sin(ang), 0)
		local start = cf * CFrame.new(x, 0, 0)
		local target = start * CFrame.new(dir * (len * 0.5 + (o.Offset or 0)))
		local rot = CFrame.fromMatrix(Vector3.zero, Vector3.new(0, 0, 1):Cross(dir), dir)
		local width = len * rng:NextNumber(0.05, 0.1)
		local mesh = VFX.Mesh("Shard", 1)
		local part: BasePart
		if mesh then
			part = mesh
			mesh.Color = o.Color or BLACK
		else
			part = VFX.Part({ ClassName = "WedgePart", Color = o.Color or BLACK })
		end
		local finalSize = if mesh then Vector3.new(width * 1.5, width * 0.4, len) else Vector3.new(0.12, len, width)
		local orient = if mesh then CFrame.lookAt(Vector3.zero, dir) else rot
		VFX.Animate(dur, function(a)
			local grow = outQuint(math.min(a / 0.18, 1))
			part.Size = finalSize * Vector3.new(1, if mesh then 1 else grow, if mesh then grow else 1)
				+ Vector3.new(0.01, 0.01, 0.01)
			local pos = start.Position:Lerp(target.Position, grow)
			part.CFrame = CFrame.new(pos) * (cf.Rotation * orient)
			part.Transparency = if a < 0.45 then 0 else (a - 0.45) / 0.55
			if a >= 1 then
				part:Destroy()
			end
		end)
	end
end

-- -------------------------------------------------------------- darbe yıldızı

function VFX.ImpactStar(position: Vector3, size: number?, color: Color3?)
	local cam = workspace.CurrentCamera
	local s = size or 4
	local look = if cam then CFrame.lookAt(position, cam.CFrame.Position) else CFrame.new(position)
	local frame = look * CFrame.Angles(0, 0, math.random() * math.pi * 2)
	local mesh = VFX.Mesh("ImpactStar", s / 1.84)
	if mesh then
		local s0 = mesh.Size
		mesh.Color = color or BLACK
		local h = outline(mesh, 0.1)
		VFX.Animate(0.24, function(a)
			local k = if a < 0.2 then outQuint(a / 0.2) * 1.15 else 1.15 - 0.4 * (a - 0.2) / 0.8
			mesh.Size = s0 * math.max(k, 0.01)
			mesh.CFrame = frame * VFX.MeshOffset("ImpactStar")
			mesh.Transparency = if a < 0.5 then 0 else (a - 0.5) * 2
			if h then
				h.OutlineTransparency = 0.1 + 0.9 * a
			end
			if a >= 1 then
				mesh:Destroy()
			end
		end)
		return
	end
	local spikes = {}
	for i = 1, 7 do
		local ang = (i / 7) * math.pi * 2 + math.random() * 0.4
		local len = s * (0.55 + math.random() * 0.45)
		local dir = Vector3.new(math.cos(ang), math.sin(ang), 0)
		local p = VFX.Part({ ClassName = "WedgePart", Size = Vector3.new(0.1, 0.1, 0.1), Color = color or BLACK })
		table.insert(spikes, { part = p, dir = dir, len = len })
	end
	VFX.Animate(0.22, function(a)
		local k = if a < 0.25 then outQuint(a / 0.25) else 1
		for _, sp in ipairs(spikes) do
			local l = sp.len * k
			local rot = CFrame.fromMatrix(Vector3.zero, Vector3.new(0, 0, 1):Cross(sp.dir), sp.dir)
			sp.part.Size = Vector3.new(0.1, math.max(l, 0.05), sp.len * 0.16)
			sp.part.CFrame = frame * CFrame.new(sp.dir * l * 0.5) * rot
			sp.part.Transparency = if a < 0.55 then 0 else (a - 0.55) / 0.45
			if a >= 1 then
				sp.part:Destroy()
			end
		end
	end)
end

-- ------------------------------------------------------------------ gölge-iz

function VFX.Afterimage(character: Model, opts: { [string]: any }?)
	opts = opts or {}
	local o = opts :: any
	local life = o.Lifetime or 0.35
	local t0 = o.Transparency or 0.25
	local folder = Instance.new("Model")
	folder.Name = "YamiAfterimage"
	for _, d in ipairs(character:GetDescendants()) do
		if d:IsA("BasePart") and d.Transparency < 0.9 and d.Name ~= "HumanoidRootPart" then
			local copy: BasePart?
			if d.Archivable then
				local ok, c = pcall(function()
					return d:Clone()
				end)
				if ok and c then
					copy = c
					c:ClearAllChildren()
				end
			end
			if copy == nil then
				copy = Instance.new("Part")
				copy.Size = d.Size
			end
			local c = copy :: BasePart
			c.Anchored = true
			c.CanCollide = false
			c.CanQuery = false
			c.CanTouch = false
			c.CastShadow = false
			c.Massless = true
			c.CFrame = d.CFrame
			c.Color = o.Color or BLACK
			c.Material = Enum.Material.Neon
			c.Transparency = t0
			if c:IsA("MeshPart") then
				c.TextureID = ""
			end
			c.Parent = folder
		end
	end
	folder.Parent = VFX.Folder()
	local list = folder:GetChildren()
	VFX.Animate(life, function(a)
		for _, p in ipairs(list) do
			(p :: BasePart).Transparency = t0 + (1 - t0) * a
		end
		if a >= 1 then
			folder:Destroy()
		end
	end)
end

-- --------------------------------------------------------------- zemin izleri

-- Yerde uzun siyah yarık (kesik izi)
function VFX.GroundScar(from: Vector3, to: Vector3, width: number, lifetime: number, groundY: number?)
	local dir = to - from
	local len = dir.Magnitude
	if len < 0.5 then
		return
	end
	local y = groundY or from.Y
	local mid = (from + to) / 2
	local cf = CFrame.lookAt(Vector3.new(mid.X, y + 0.06, mid.Z), Vector3.new(to.X, y + 0.06, to.Z))
	local p = VFX.Part({ Size = Vector3.new(width, 0.12, 0.1), CFrame = cf, Transparency = 0.05 })
	VFX.Animate(0.18, function(a)
		p.Size = Vector3.new(width * (1 - 0.3 * a), 0.12, math.max(len * outCubic(a), 0.1))
	end)
	VFX.FadeDestroy(p, 1.2, lifetime)
end

-- Yerde merkezden dışa doğru siyah çatlaklar
function VFX.GroundCracks(center: Vector3, count: number, length: number, lifetime: number, seed: number?)
	local rng = Random.new(seed or 1)
	for i = 1, count do
		local ang = (i / count) * math.pi * 2 + rng:NextNumber(-0.3, 0.3)
		local dir = Vector3.new(math.cos(ang), 0, math.sin(ang))
		local segs = 3
		local pos = center
		for s = 1, segs do
			local segLen = length / segs * rng:NextNumber(0.7, 1.3)
			dir = (CFrame.Angles(0, rng:NextNumber(-0.5, 0.5), 0) * CFrame.new(dir)).Position.Unit
			local nextPos = pos + dir * segLen
			local mid = (pos + nextPos) / 2
			local p = VFX.Part({
				Size = Vector3.new(0.35 * (1 - (s - 1) / segs) + 0.1, 0.1, 0.1),
				CFrame = CFrame.lookAt(mid, nextPos),
				Transparency = 0.02,
			})
			local final = Vector3.new(p.Size.X, 0.1, segLen)
			task.delay((s - 1) * 0.05, function()
				VFX.Tween(p, 0.12, { Size = final })
			end)
			VFX.FadeDestroy(p, 0.8, lifetime)
			pos = nextPos
		end
	end
end

-- Kalıcı aura (parçacık yayıcı) - dönen emitter'ı :Destroy() ile kaldır
function VFX.Aura(parent: Instance, preset: string, overrides: { [string]: any }?): ParticleEmitter
	local e = VFX.Emitter(parent, preset, overrides)
	e.Enabled = true
	return e
end

return VFX
