-- Ortak yardımcı fonksiyonlar (server + client)
local Players = game:GetService("Players")

local Util = {}

function Util.getHumanoid(model: Instance?): Humanoid?
	if model == nil then
		return nil
	end
	return model:FindFirstChildOfClass("Humanoid")
end

function Util.getRoot(model: Instance?): BasePart?
	if model == nil then
		return nil
	end
	local root = model:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		return root
	end
	return nil
end

function Util.isAlive(model: Instance?): boolean
	local hum = Util.getHumanoid(model)
	return hum ~= nil and hum.Health > 0 and model ~= nil and model.Parent ~= nil
end

-- Yatay (Y=0) birim vektör; geçersizse nil
function Util.flat(v: Vector3?): Vector3?
	if typeof(v) ~= "Vector3" then
		return nil
	end
	local f = Vector3.new(v.X, 0, v.Z)
	local m = f.Magnitude
	if m < 1e-3 or m ~= m then
		return nil
	end
	return f / m
end

function Util.isFiniteVector(v: any): boolean
	if typeof(v) ~= "Vector3" then
		return false
	end
	for _, c in ipairs({ v.X, v.Y, v.Z }) do
		if c ~= c or c == math.huge or c == -math.huge then
			return false
		end
	end
	return true
end

function Util.characterList(): { Instance }
	local list = {}
	for _, p in ipairs(Players:GetPlayers()) do
		if p.Character then
			table.insert(list, p.Character)
		end
	end
	return list
end

-- Zemin bilgisi: pozisyon, normal, materyal, renk
function Util.ground(position: Vector3, ignore: { Instance }?, depth: number?)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.IgnoreWater = true
	local list = Util.characterList()
	if ignore then
		for _, inst in ipairs(ignore) do
			table.insert(list, inst)
		end
	end
	local fx = workspace:FindFirstChild("YamiFX")
	if fx then
		table.insert(list, fx)
	end
	params.FilterDescendantsInstances = list
	local result = workspace:Raycast(position + Vector3.new(0, 4, 0), Vector3.new(0, -(depth or 40), 0), params)
	if result == nil then
		return nil
	end
	local material = result.Material
	local color: Color3
	local inst = result.Instance
	if inst:IsA("Terrain") then
		local ok, c = pcall(function()
			return workspace.Terrain:GetMaterialColor(material)
		end)
		color = if ok then c else Color3.fromRGB(95, 92, 88)
	elseif inst:IsA("BasePart") then
		color = inst.Color
	else
		color = Color3.fromRGB(95, 92, 88)
	end
	if
		material == Enum.Material.Water
		or material == Enum.Material.Air
		or material == Enum.Material.Neon
		or material == Enum.Material.ForceField
		or material == Enum.Material.Glass
	then
		material = Enum.Material.Slate
	end
	return {
		Position = result.Position,
		Normal = result.Normal,
		Material = material,
		Color = color,
		Instance = inst,
	}
end

function Util.randomUnitXZ(rng: Random): Vector3
	local a = rng:NextNumber(0, math.pi * 2)
	return Vector3.new(math.cos(a), 0, math.sin(a))
end

return Util
