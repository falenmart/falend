-- ShopServer (Script)
-- Konum: ServerScriptService > ShopServer
--
-- Coin, satın alma, kuşanma ve kayıt işlemleri sunucuda yapılır;
-- istemci sadece istek gönderir, böylece hile ile eşya alınamaz.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local DataStoreService = game:GetService("DataStoreService")
local MarketplaceService = game:GetService("MarketplaceService")

local ShopItems = require(ReplicatedStorage:WaitForChild("ShopItems"))
local Settings = ShopItems.Settings

-- Remote'lar
local remotes = Instance.new("Folder")
remotes.Name = "ShopRemotes"

local purchaseRemote = Instance.new("RemoteFunction")
purchaseRemote.Name = "Purchase"
purchaseRemote.Parent = remotes

local equipRemote = Instance.new("RemoteFunction")
equipRemote.Name = "Equip"
equipRemote.Parent = remotes

local getDataRemote = Instance.new("RemoteFunction")
getDataRemote.Name = "GetData"
getDataRemote.Parent = remotes

local dataChanged = Instance.new("RemoteEvent")
dataChanged.Name = "DataChanged"
dataChanged.Parent = remotes

remotes.Parent = ReplicatedStorage

local dataStore
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(Settings.DataStoreName)
	end)
	if ok then
		dataStore = result
	else
		warn("[Mağaza] DataStore kullanılamıyor, veriler kaydedilmeyecek:", result)
	end
end

-- [Player] = { Owned = { [itemId] = true }, Equipped = { [category] = itemId }, LoadFailed = bool }
local profiles = {}
local warnedMissingTools = {}

local function getCoins(player)
	local leaderstats = player:FindFirstChild("leaderstats")
	return leaderstats and leaderstats:FindFirstChild(Settings.CurrencyName)
end

local function sync(player)
	local profile = profiles[player]
	if profile then
		dataChanged:FireClient(player, { Owned = profile.Owned, Equipped = profile.Equipped })
	end
end

local function getCoinMultiplier(profile)
	local multiplier = 1
	for _, itemId in pairs(profile.Equipped) do
		local item = ShopItems.ById[itemId]
		if item and item.Boost and item.Boost.CoinMultiplier then
			multiplier *= item.Boost.CoinMultiplier
		end
	end
	return multiplier
end

----------------------------------------------------------------------
-- Kuşanılan eşyaları karaktere uygula
----------------------------------------------------------------------

local function clearShopObjects(player)
	for _, container in ipairs({ player:FindFirstChildOfClass("Backpack"), player.Character }) do
		for _, obj in ipairs(container and container:GetDescendants() or {}) do
			if obj:GetAttribute("ShopObject") then
				obj:Destroy()
			end
		end
	end
end

local function giveTool(player, item)
	local folder = ServerStorage:FindFirstChild("ShopTools")
	local tool = folder and folder:FindFirstChild(item.Id)
	if not (tool and tool:IsA("Tool")) then
		if not warnedMissingTools[item.Id] then
			warnedMissingTools[item.Id] = true
			warn(("[Mağaza] ServerStorage.ShopTools içinde '%s' adlı bir Tool yok, silah verilemedi."):format(item.Id))
		end
		return
	end
	local backpack = player:FindFirstChildOfClass("Backpack")
	if backpack then
		local clone = tool:Clone()
		clone:SetAttribute("ShopObject", true)
		clone.Parent = backpack
	end
end

local function spawnPet(character, root, item)
	local offset = CFrame.new(2.5, 1.5, 2)

	local pet = Instance.new("Part")
	pet.Name = "ShopPet"
	pet.Size = Vector3.new(1, 1, 1)
	pet.Transparency = 1
	pet.CanCollide = false
	pet.CanQuery = false
	pet.CanTouch = false
	pet.Massless = true
	pet.CFrame = root.CFrame * offset
	pet:SetAttribute("ShopObject", true)

	local weld = Instance.new("Weld")
	weld.Part0 = root
	weld.Part1 = pet
	weld.C0 = offset
	weld.Parent = pet

	local billboard = Instance.new("BillboardGui")
	billboard.Size = UDim2.fromScale(2.5, 2.5) -- stud cinsinden
	billboard.LightInfluence = 0
	billboard.Parent = pet

	local icon = Instance.new("TextLabel")
	icon.BackgroundTransparency = 1
	icon.Size = UDim2.fromScale(1, 1)
	icon.Text = item.Icon
	icon.TextScaled = true
	icon.Parent = billboard

	pet.Parent = character
end

local function addEffect(root, item)
	local effect = Instance.new(item.Effect)
	for property, value in pairs(item.EffectProps or {}) do
		effect[property] = value
	end
	effect:SetAttribute("ShopObject", true)
	effect.Parent = root
end

local function applyEquipment(player)
	local profile = profiles[player]
	local character = player.Character
	if not profile or not character then
		return
	end
	clearShopObjects(player)

	local humanoid = character:FindFirstChildOfClass("Humanoid")
	local root = character:FindFirstChild("HumanoidRootPart")
	if humanoid then
		humanoid.WalkSpeed = Settings.DefaultWalkSpeed
		humanoid.UseJumpPower = true
		humanoid.JumpPower = Settings.DefaultJumpPower
	end

	for _, itemId in pairs(profile.Equipped) do
		local item = ShopItems.ById[itemId]
		if item then
			if item.Tool then
				giveTool(player, item)
			end
			if item.Boost and humanoid then
				humanoid.WalkSpeed = item.Boost.WalkSpeed or humanoid.WalkSpeed
				humanoid.JumpPower = item.Boost.JumpPower or humanoid.JumpPower
			end
			if item.Pet and root then
				spawnPet(character, root, item)
			end
			if item.Effect and root then
				addEffect(root, item)
			end
		end
	end
end

----------------------------------------------------------------------
-- Kayıt / yükleme
----------------------------------------------------------------------

local function dataKey(player)
	return "player_" .. player.UserId
end

local function loadProfile(player)
	local data, loadFailed = nil, false
	if dataStore then
		local ok, result = pcall(function()
			return dataStore:GetAsync(dataKey(player))
		end)
		if ok then
			data = result
		else
			loadFailed = true
			warn("[Mağaza] Veri yüklenemedi:", player.Name, result)
		end
	end
	data = data or {}

	local profile = { Owned = {}, Equipped = {}, LoadFailed = loadFailed }
	for _, itemId in ipairs(data.Owned or {}) do
		if ShopItems.ById[itemId] then
			profile.Owned[itemId] = true
		end
	end
	for _, item in ipairs(ShopItems.Items) do
		if item.Price == 0 then
			profile.Owned[item.Id] = true
		end
	end

	if data.Equipped then
		for category, itemId in pairs(data.Equipped) do
			if profile.Owned[itemId] then
				profile.Equipped[category] = itemId
			end
		end
	else
		-- İlk giriş: ücretsiz eşyaları kuşan
		for _, item in ipairs(ShopItems.Items) do
			if item.Price == 0 and not profile.Equipped[item.Category] then
				profile.Equipped[item.Category] = item.Id
			end
		end
	end

	return profile, data.Coins or Settings.StartingCoins
end

local function saveProfile(player)
	local profile = profiles[player]
	local coins = getCoins(player)
	-- Yükleme başarısız olduysa üzerine yazıp veriyi silmeyelim
	if not dataStore or not profile or profile.LoadFailed or not coins then
		return
	end

	local owned = {}
	for itemId in pairs(profile.Owned) do
		table.insert(owned, itemId)
	end
	local payload = { Coins = coins.Value, Owned = owned, Equipped = profile.Equipped }

	local ok, err = pcall(function()
		dataStore:SetAsync(dataKey(player), payload)
	end)
	if not ok then
		warn("[Mağaza] Veri kaydedilemedi:", player.Name, err)
	end
end

----------------------------------------------------------------------
-- Oyuncu giriş / çıkış
----------------------------------------------------------------------

local function onCharacterAdded(player, character)
	character:WaitForChild("Humanoid")
	character:WaitForChild("HumanoidRootPart")
	player:WaitForChild("Backpack")
	task.wait() -- StarterPack kopyalanırken araçlarımız silinmesin
	applyEquipment(player)
end

local function onPlayerAdded(player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"

	local coins = Instance.new("IntValue")
	coins.Name = Settings.CurrencyName
	coins.Parent = leaderstats

	local profile, savedCoins = loadProfile(player)
	if not player.Parent then
		return
	end
	coins.Value = savedCoins
	leaderstats.Parent = player
	profiles[player] = profile
	sync(player)

	player.CharacterAdded:Connect(function(character)
		onCharacterAdded(player, character)
	end)
	if player.Character then
		task.spawn(onCharacterAdded, player, player.Character)
	end
end

Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(onPlayerAdded, player)
end

Players.PlayerRemoving:Connect(function(player)
	saveProfile(player)
	profiles[player] = nil
end)

game:BindToClose(function()
	for _, player in ipairs(Players:GetPlayers()) do
		task.spawn(saveProfile, player)
	end
	task.wait(3)
end)

-- Otomatik kayıt
task.spawn(function()
	while true do
		task.wait(120)
		for player in pairs(profiles) do
			task.spawn(saveProfile, player)
		end
	end
end)

-- Pasif gelir
if Settings.PassiveIncome.Amount > 0 then
	task.spawn(function()
		while true do
			task.wait(Settings.PassiveIncome.Interval)
			for player, profile in pairs(profiles) do
				local coins = getCoins(player)
				if coins then
					coins.Value += Settings.PassiveIncome.Amount * getCoinMultiplier(profile)
				end
			end
		end
	end)
end

----------------------------------------------------------------------
-- Remote işleyiciler
----------------------------------------------------------------------

local function validate(player, itemId)
	if typeof(itemId) ~= "string" then
		return nil, nil, "Geçersiz istek."
	end
	local profile = profiles[player]
	if not profile then
		return nil, nil, "Verilerin henüz yüklenmedi."
	end
	local item = ShopItems.ById[itemId]
	if not item then
		return nil, nil, "Eşya bulunamadı."
	end
	return profile, item
end

purchaseRemote.OnServerInvoke = function(player, itemId)
	local profile, item, err = validate(player, itemId)
	if err then
		return { ok = false, message = err }
	end
	if profile.Owned[item.Id] then
		return { ok = false, message = "Bu eşyaya zaten sahipsin." }
	end

	local coins = getCoins(player)
	if not coins or coins.Value < item.Price then
		local missing = item.Price - (coins and coins.Value or 0)
		return { ok = false, message = ("Yetersiz coin! %d coin daha lazım."):format(missing) }
	end

	coins.Value -= item.Price
	profile.Owned[item.Id] = true
	if Settings.AutoEquipOnPurchase then
		profile.Equipped[item.Category] = item.Id
		applyEquipment(player)
	end
	sync(player)
	return { ok = true, message = item.Name .. " satın alındı!" }
end

equipRemote.OnServerInvoke = function(player, itemId)
	local profile, item, err = validate(player, itemId)
	if err then
		return { ok = false, message = err }
	end
	if not profile.Owned[item.Id] then
		return { ok = false, message = "Bu eşyaya sahip değilsin." }
	end

	local message
	if profile.Equipped[item.Category] == item.Id then
		profile.Equipped[item.Category] = nil
		message = item.Name .. " çıkarıldı."
	else
		profile.Equipped[item.Category] = item.Id
		message = item.Name .. " kuşanıldı!"
	end
	applyEquipment(player)
	sync(player)
	return { ok = true, message = message }
end

getDataRemote.OnServerInvoke = function(player)
	while not profiles[player] and player.Parent do
		task.wait(0.1)
	end
	local profile = profiles[player]
	return profile and { Owned = profile.Owned, Equipped = profile.Equipped }
end

-- Robux ile coin satışı (Settings.CoinProduct.Id ayarlandıysa)
-- Not: Oyununda başka bir ProcessReceipt varsa ikisini birleştirmen gerekir.
if Settings.CoinProduct.Id ~= 0 then
	MarketplaceService.ProcessReceipt = function(receipt)
		if receipt.ProductId ~= Settings.CoinProduct.Id then
			return Enum.ProductPurchaseDecision.NotProcessedYet
		end
		local player = Players:GetPlayerByUserId(receipt.PlayerId)
		local coins = player and getCoins(player)
		if not coins then
			return Enum.ProductPurchaseDecision.NotProcessedYet
		end
		coins.Value += Settings.CoinProduct.Amount
		task.spawn(saveProfile, player)
		return Enum.ProductPurchaseDecision.PurchaseGranted
	end
end
