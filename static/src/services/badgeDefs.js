angular.module('badgeDefs', [
])

    .factory("BadgeDefs", function($http){

      var data = []

      function load(){

        var url = "/api/badges"
        console.log("getting badge defs ")

        return $http.get(url).success(function(resp){

          // clear the data object
          data.length = 0

          // put the response in the data object
          _.each(resp.list, function(v){
            data.push(v)
          })

        })
      }

      return {
        d: data,
        load: load
      }
    })