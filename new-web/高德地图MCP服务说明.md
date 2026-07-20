能力介绍
地理编码
将详细的结构化地址转换为经纬度坐标。

输入

address (位置信息)，city (城市信息，非必须)

输出

location (位置经纬度)

逆地理编码
将一个高德经纬度坐标转换为行政区划地址信息。

输入

location (位置经纬度)

输出

addressComponent (位置信息，包括省市区等信息)

IP 定位
IP 定位根据用户输入的 IP 地址，定位 IP 的所在位置。

输入

IP

输出

province (省)，city (城市)，adcode (城市编码)

天气查询
根据城市名称或者标准adcode查询指定城市的天气。

输入

city (城市名称或城市adcode)

输出

forecasts (预报天气)

骑行路径规划
用于规划骑行通勤方案，规划时会考虑天桥、单行线、封路等情况。最大支持 500km 的骑行路线规划。

输入

origin (起点经纬度)，destination (终点经纬度)

输出

distance (规划距离)，duration (规划时间)，steps (规划步骤信息)

步行路径规划
可以根据输入起点终点经纬度坐标，规划100km 以内的步行通勤方案，并且返回通勤方案的数据。

输入

origin (起点经纬度)，destination (终点经纬度)

输出

origin (起点信息)，destination (终点信息)，paths (规划具体信息)

驾车路径规划
根据用户起终点经纬度坐标规划以小客车、轿车通勤出行的方案，并且返回通勤方案的数据。

输入

origin (起点经纬度)，destination (终点经纬度)

输出

origin (起点信息)，destination (终点信息)，paths (规划具体信息)

公交路径规划
根据用户起终点经纬度坐标规划综合各类公共（火车、公交、地铁）交通方式的通勤方案，并且返回通勤方案的数据，跨城场景下必须传起点城市与终点城市。

输入

origin (起点经纬度)，destination (终点经纬度)，city (起点城市)，cityd (终点城市)

输出

origin (起点信息)，destination (终点信息)，distance (规划距离)，transits (规划具体信息)

距离测量
测量两个经纬度坐标之间的距离。

输入

origin (起点经纬度)，destination (终点经纬度)

输出

origin_id (起点信息)，dest_id (终点信息)，distance (规划距离)，duration (时间)

关键词搜索
根据用户传入关键词，搜索出相关的POI地点信息。

输入

keywords (搜索关键词)，city (查询城市，非必须)

输出

suggestion (搜索建议)，pois (地点信息列表)

周边搜索
根据用户传入关键词以及坐标location，搜索出radius半径范围的POI地点信息。

输入

keywords (搜索关键词)，location (中心点经度纬度)，radius (搜索半径，非必须)

输出

pois (地点信息列表)

详情搜索
查询关键词搜或者周边搜获取到的POI ID的详细信息。

输入

id (关键词搜或周边搜获取的poiid)

输出

地点详情信息

location (地点经纬度)，address (地址)，business_area (商圈)，city(城市)，type (地点类型) 等