--[[
	SFX (client) - Config.Sounds içindeki sesleri 3D olarak çalar.
	SFX.Play(name, at, opts) -> Sound   (at: BasePart / Attachment / Vector3 / nil = 2D)
]]
local Debris = game:GetService("Debris")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")

local Config = require(script.Parent:WaitForChild("Config"))

local SFX = {}

function SFX.Play(name: string, at: any?, opts: { [string]: any }?): Sound?
	local def = Config.Sounds[name]
	if def == nil or def.Id == nil or def.Id == "" then
		return nil
	end
	local o = (opts or {}) :: any
	local s = Instance.new("Sound")
	s.Name = "Yami" .. name
	s.SoundId = def.Id
	s.Volume = (def.Volume or 1) * (o.Volume or 1)
	s.PlaybackSpeed = (def.Speed or 1) * (o.Speed or 1)
	s.Looped = def.Looped == true
	s.RollOffMaxDistance = o.MaxDistance or 260
	s.RollOffMinDistance = 12
	if def.Reverb then
		local r = Instance.new("ReverbSoundEffect")
		r.DecayTime = 2.2
		r.WetLevel = -4
		r.Parent = s
		local eq = Instance.new("EqualizerSoundEffect")
		eq.LowGain = 6
		eq.MidGain = 0
		eq.HighGain = -6
		eq.Parent = s
	end
	local holder: Instance? = nil
	if typeof(at) == "Instance" then
		s.Parent = at
	elseif typeof(at) == "Vector3" then
		local a = Instance.new("Attachment")
		a.Name = "YamiSoundPoint"
		a.Parent = workspace.Terrain
		a.WorldPosition = at
		s.Parent = a
		holder = a
	else
		s.Parent = SoundService
	end
	if def.StartTime then
		s.TimePosition = def.StartTime
	end
	s:Play()
	local dur = o.Duration or def.Duration
	if dur and not s.Looped then
		task.delay(dur * 0.7, function()
			if s.Parent then
				TweenService:Create(s, TweenInfo.new(dur * 0.3), { Volume = 0 }):Play()
			end
		end)
		Debris:AddItem(s, dur + 0.1)
		if holder then
			Debris:AddItem(holder, dur + 0.2)
		end
	elseif not s.Looped then
		s.Ended:Connect(function()
			s:Destroy()
			if holder then
				holder:Destroy()
			end
		end)
		Debris:AddItem(s, 10)
		if holder then
			Debris:AddItem(holder, 10)
		end
	end
	return s
end

function SFX.FadeOut(s: Sound?, t: number?)
	if s == nil or s.Parent == nil then
		return
	end
	local tw = TweenService:Create(s, TweenInfo.new(t or 0.4), { Volume = 0 })
	tw:Play()
	tw.Completed:Connect(function()
		s:Destroy()
	end)
end

return SFX
