--[[
	ScreenFX (client) - ekran efektleri
	ImpactFrames : manga tarzı siyah-beyaz darbe kareleri
	Darken       : şarj sırasında dünyayı karartır (handle:Release())
	FOVKick      : görüş açısı vuruşu
	ScreenSlash  : ekranı boydan boya kesen siyah yarık (boyut kesiği)
	Vignette     : kenarlardan kararma
	Flash        : tam ekran renk flaşı
]]
local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")

local Config = require(script.Parent:WaitForChild("Config"))

local ScreenFX = {}

local function tween(
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

local function cc(name: string): ColorCorrectionEffect
	local e = Instance.new("ColorCorrectionEffect")
	e.Name = name
	e.Parent = Lighting
	return e
end

local gui: ScreenGui? = nil
local function getGui(): ScreenGui
	if gui and gui.Parent then
		return gui
	end
	local player = Players.LocalPlayer
	local g = Instance.new("ScreenGui")
	g.Name = "YamiScreenFX"
	g.IgnoreGuiInset = true
	g.ResetOnSpawn = false
	g.DisplayOrder = 50
	g.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	g.Parent = player:WaitForChild("PlayerGui")
	gui = g
	return g
end

-- Manga darbe kareleri: [koyu kontrast] -> [beyaz patlama] -> normale dönüş
function ScreenFX.ImpactFrames(strength: number?)
	if not (Config.Screen.ImpactFrames and Config.Screen.ColorEffects) then
		return
	end
	local s = strength or 1
	local e = cc("YamiImpactFrame")
	e.Saturation = -1
	e.Contrast = 2.2 * s
	e.Brightness = -0.28 * s
	task.delay(0.055, function()
		e.Contrast = 3 * s
		e.Brightness = 0.32 * s
		task.delay(0.05, function()
			e.Contrast = 1.6 * s
			e.Brightness = -0.12 * s
			local tw = tween(e, 0.32, { Contrast = 0, Brightness = 0, Saturation = 0 })
			tw.Completed:Connect(function()
				e:Destroy()
			end)
		end)
	end)
end

function ScreenFX.Monochrome(duration: number, strength: number?)
	if not Config.Screen.ColorEffects then
		return
	end
	local e = cc("YamiMono")
	local s = strength or 1
	tween(e, 0.08, { Saturation = -1 * s, Contrast = 0.6 * s })
	task.delay(duration, function()
		local tw = tween(e, 0.35, { Saturation = 0, Contrast = 0 })
		tw.Completed:Connect(function()
			e:Destroy()
		end)
	end)
end

-- Şarj sırasında sahneyi karart. Dönen handle ile geri al.
function ScreenFX.Darken(amount: number, fadeIn: number)
	local handle = {}
	if not Config.Screen.ColorEffects then
		function handle.Release() end
		return handle
	end
	local e = cc("YamiDarken")
	tween(e, fadeIn, {
		Brightness = -0.18 * amount,
		Saturation = -0.65 * amount,
		Contrast = 0.25 * amount,
		TintColor = Color3.new(1, 1, 1):Lerp(Color3.fromRGB(150, 140, 175), amount * 0.6),
	}, Enum.EasingStyle.Sine)
	local released = false
	function handle.Release(_, fadeOut: number?)
		if released then
			return
		end
		released = true
		local tw =
			tween(e, fadeOut or 0.6, { Brightness = 0, Saturation = 0, Contrast = 0, TintColor = Color3.new(1, 1, 1) })
		tw.Completed:Connect(function()
			e:Destroy()
		end)
	end
	task.delay(12, function()
		handle:Release()
	end)
	return handle
end

local fovBase: number? = nil
local fovTweens = 0
function ScreenFX.FOVKick(delta: number, inTime: number, outTime: number)
	if not Config.Screen.FieldOfViewKick then
		return
	end
	local cam = workspace.CurrentCamera
	if cam == nil then
		return
	end
	if fovTweens == 0 then
		fovBase = cam.FieldOfView
	end
	fovTweens += 1
	local base = fovBase or 70
	tween(
		cam,
		inTime,
		{ FieldOfView = math.clamp(base + delta, 20, 110) },
		Enum.EasingStyle.Quad,
		Enum.EasingDirection.Out
	)
	task.delay(inTime, function()
		local tw = tween(cam, outTime, { FieldOfView = base }, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut)
		tw.Completed:Connect(function()
			fovTweens -= 1
		end)
	end)
end

function ScreenFX.Flash(color: Color3, alpha: number, duration: number)
	local g = getGui()
	local f = Instance.new("Frame")
	f.Name = "Flash"
	f.BackgroundColor3 = color
	f.BackgroundTransparency = 1 - alpha
	f.BorderSizePixel = 0
	f.Size = UDim2.fromScale(1, 1)
	f.ZIndex = 5
	f.Parent = g
	local tw = tween(f, duration, { BackgroundTransparency = 1 })
	tw.Completed:Connect(function()
		f:Destroy()
	end)
end

local function edgeGradient(parent: Instance, rotation: number, alpha: number)
	local f = Instance.new("Frame")
	f.BackgroundColor3 = Color3.new(0, 0, 0)
	f.BorderSizePixel = 0
	f.Size = UDim2.fromScale(1, 1)
	f.BackgroundTransparency = 0
	local g = Instance.new("UIGradient")
	g.Rotation = rotation
	g.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 1 - alpha),
		NumberSequenceKeypoint.new(0.28, 1),
		NumberSequenceKeypoint.new(1, 1),
	})
	g.Parent = f
	f.Parent = parent
	return f
end

function ScreenFX.Vignette(alpha: number, duration: number)
	local g = getGui()
	local holder = Instance.new("CanvasGroup")
	holder.Name = "Vignette"
	holder.BackgroundTransparency = 1
	holder.Size = UDim2.fromScale(1, 1)
	holder.GroupTransparency = 1
	holder.Parent = g
	for _, r in ipairs({ 0, 90, 180, 270 }) do
		edgeGradient(holder, r, alpha)
	end
	tween(holder, 0.12, { GroupTransparency = 0 })
	task.delay(duration, function()
		local tw = tween(holder, 0.45, { GroupTransparency = 1 })
		tw.Completed:Connect(function()
			holder:Destroy()
		end)
	end)
end

--[[
	Ekranı kesen yarık: ince siyah çizgi bir anda ekranı boydan boya geçer, açılır (kalınlaşır),
	beyaz kenarlarla titrer ve kapanır. angle derece (0 = yatay).
]]
function ScreenFX.ScreenSlash(angle: number, holdTime: number?)
	if not Config.Screen.ScreenSlash then
		return
	end
	local g = getGui()
	local root = Instance.new("Frame")
	root.Name = "ScreenSlash"
	root.AnchorPoint = Vector2.new(0.5, 0.5)
	root.Position = UDim2.fromScale(0.5, 0.5)
	root.Size = UDim2.new(3, 0, 0, 0)
	root.Rotation = angle
	root.BackgroundColor3 = Color3.new(0, 0, 0)
	root.BorderSizePixel = 0
	root.ZIndex = 10
	root.Parent = g
	local stroke = Instance.new("UIStroke")
	stroke.Color = Config.Theme.Accent
	stroke.Thickness = 2
	stroke.Transparency = Config.Theme.OutlineTransparency
	stroke.Parent = root
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(1, 0)
	corner.Parent = root
	-- 1) ince çizgi (anında)
	root.Size = UDim2.new(0, 0, 0, 3)
	tween(root, 0.06, { Size = UDim2.new(3, 0, 0, 4) }, Enum.EasingStyle.Quart)
	-- 2) yarık açılır
	task.delay(0.08, function()
		tween(root, 0.12, { Size = UDim2.new(3, 0, 0, 38) }, Enum.EasingStyle.Back)
		-- kırık parçalar
		for i = 1, 6 do
			local shard = Instance.new("Frame")
			shard.BackgroundColor3 = Color3.new(0, 0, 0)
			shard.BorderSizePixel = 0
			shard.AnchorPoint = Vector2.new(0.5, 0.5)
			local along = (i - 3.5) / 3.5 * 0.42
			shard.Position =
				UDim2.fromScale(0.5 + along * math.cos(math.rad(angle)), 0.5 + along * math.sin(math.rad(angle)))
			shard.Size = UDim2.new(0, math.random(40, 120), 0, math.random(3, 7))
			shard.Rotation = angle + math.random(-35, 35)
			shard.ZIndex = 9
			shard.Parent = g
			local s2 = Instance.new("UIStroke")
			s2.Color = Config.Theme.Accent
			s2.Transparency = 0.5
			s2.Parent = shard
			local tw = tween(shard, 0.5, { BackgroundTransparency = 1, Size = UDim2.new(0, 0, 0, 2) })
			tween(s2, 0.5, { Transparency = 1 })
			tw.Completed:Connect(function()
				shard:Destroy()
			end)
		end
	end)
	-- 3) kapanış
	task.delay(0.2 + (holdTime or 0.25), function()
		local tw = tween(root, 0.22, { Size = UDim2.new(3, 0, 0, 0) }, Enum.EasingStyle.Quart, Enum.EasingDirection.In)
		tween(stroke, 0.22, { Transparency = 1 })
		tw.Completed:Connect(function()
			root:Destroy()
		end)
	end)
end

-- Hızlı yardımcı: yakında mı? (başkalarının yeteneklerinde ekran efektini mesafeye göre aç)
function ScreenFX.InRange(position: Vector3, radius: number?): boolean
	local cam = workspace.CurrentCamera
	if cam == nil then
		return false
	end
	return (cam.CFrame.Position - position).Magnitude <= (radius or Config.Screen.EffectRadius)
end

return ScreenFX
