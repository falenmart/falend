--[[
	DemoDummies (Script) - sadece demo yeri için: denemelik R15 mankenler oluşturur,
	ölünce birkaç saniye sonra yeniden doğurur. Kendi oyununa koymana gerek yok.
]]
local Players = game:GetService("Players")

local SPOTS = {
	Vector3.new(-12, 4, 5),
	Vector3.new(0, 4, 0),
	Vector3.new(12, 4, 5),
	Vector3.new(-20, 4, -22),
	Vector3.new(-6, 4, -28),
	Vector3.new(8, 4, -28),
	Vector3.new(22, 4, -22),
	Vector3.new(0, 4, -60),
}

local function createRig(): Model?
	local desc = Instance.new("HumanoidDescription")
	desc.HeadColor = Color3.fromRGB(200, 200, 205)
	desc.TorsoColor = Color3.fromRGB(90, 90, 98)
	desc.LeftArmColor = Color3.fromRGB(200, 200, 205)
	desc.RightArmColor = Color3.fromRGB(200, 200, 205)
	desc.LeftLegColor = Color3.fromRGB(60, 60, 66)
	desc.RightLegColor = Color3.fromRGB(60, 60, 66)
	local ok, rig = pcall(function()
		return Players:CreateHumanoidModelFromDescriptionAsync(desc, Enum.HumanoidRigType.R15)
	end)
	if not ok or rig == nil then
		ok, rig = pcall(function()
			return (Players :: any):CreateHumanoidModelFromDescription(desc, Enum.HumanoidRigType.R15)
		end)
	end
	if not ok or rig == nil then
		warn("[YamiDemo] Manken oluşturulamadı:", rig)
		return nil
	end
	return rig
end

local function label(rig: Model, hum: Humanoid)
	local head = rig:FindFirstChild("Head")
	if head == nil then
		return
	end
	local bb = Instance.new("BillboardGui")
	bb.Name = "DummyLabel"
	bb.Size = UDim2.new(0, 120, 0, 34)
	bb.StudsOffset = Vector3.new(0, 2.6, 0)
	bb.AlwaysOnTop = true
	bb.MaxDistance = 140
	local text = Instance.new("TextLabel")
	text.BackgroundTransparency = 1
	text.Size = UDim2.fromScale(1, 1)
	text.Font = Enum.Font.GothamBlack
	text.TextScaled = true
	text.TextColor3 = Color3.new(1, 1, 1)
	text.TextStrokeTransparency = 0.2
	text.Parent = bb
	local function refresh()
		text.Text = string.format("HEDEF  %d", math.max(0, math.floor(hum.Health + 0.5)))
	end
	hum.HealthChanged:Connect(refresh)
	refresh()
	bb.Parent = head
end

local function spawnDummy(spot: Vector3, index: number)
	local rig = createRig()
	if rig == nil then
		return
	end
	rig.Name = "Dummy" .. index
	local hum = rig:FindFirstChildOfClass("Humanoid") :: Humanoid
	hum.MaxHealth = 250
	hum.Health = 250
	hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	rig:PivotTo(CFrame.lookAt(spot, Vector3.new(0, spot.Y, 40)))
	rig.Parent = workspace
	local root = rig:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		root.Anchored = false
		pcall(function()
			root:SetNetworkOwner(nil)
		end)
	end
	label(rig, hum)
	hum.Died:Connect(function()
		task.wait(3.5)
		rig:Destroy()
		spawnDummy(spot, index)
	end)
	-- yavaş can yenileme (eğitim mankeni)
	task.spawn(function()
		while rig.Parent and hum.Health > 0 do
			task.wait(1)
			if hum.Health > 0 and hum.Health < hum.MaxHealth then
				hum.Health = math.min(hum.MaxHealth, hum.Health + 4)
			end
		end
	end)
end

for i, spot in ipairs(SPOTS) do
	task.spawn(spawnDummy, spot, i)
end
