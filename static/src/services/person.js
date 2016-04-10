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
                console.log("Person Service getting from cache:", orcidId)
                return $q.when(data)
            }


            var url = "/api/person/" + orcidId
            console.log("Person Service getting from server:", orcidId)
            return $http.get(url).success(function(resp){

                // clear the data object
                for (var member in data) delete data[member];

                // put the response in the data object
                _.each(resp, function(v, k){
                    data[k] = v
                })

                // add computed properties
                var postCounts = _.pluck(data.sources, "posts_count")
                data.numPosts = postCounts.reduce(function(a, b){return a + b}, 0)
            })
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
            reload: function(){
                return load(data.orcid_id, true)
            }
        }
    })