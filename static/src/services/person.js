angular.module('person', [
])



    .factory("Person", function($http, $q){

        var data = {}
        var badgeSortLevel = {
            "gold": 1,
            "silver": 2,
            "bronze": 3
        }
        var beltDescriptions = {
            white: "initial",
            yellow: "promising",
            orange: "notable",
            brown: "extensive",
            black: "exceptional"
        }

        function load(orcidId, force){


            // if the data for this profile is already loaded, just return it
            // unless we've been told to force a refresh from the server.
            if (data.orcid_id == orcidId && !force){
                console.log("Returning the cached Person wrapped in promise", orcidId)
                return $q.when(data)
            }


            var url = "/api/person/" + orcidId
            console.log("getting person with orcid id ", orcidId)
            return $http.get(url).success(function(resp){

                // clear the data object
                for (var member in data) delete data[member];

                // put the response in the data object
                _.each(resp, function(v, k){
                    data[k] = v
                })
            })
        }

        function getBeltInfo(){
            return {
                name: data.belt,
                descr: beltDescriptions[data.belt]
            }
        }

        function getBadgesWithConfigs(configDict) {
            var ret = []
            _.each(data.badges, function(myBadge){
                var badgeDef = configDict[myBadge.name]
                var enrichedBadge = _.extend(myBadge, badgeDef)
                enrichedBadge.sortLevel = badgeSortLevel[enrichedBadge.level]
                ret.push(enrichedBadge)
            })

            return ret
        }

        return {
            d: data,
            load: load,
            getBadgesWithConfigs: getBadgesWithConfigs,
            getBeltInfo: getBeltInfo
        }
    })