angular.module('badgeDefs', [
])

    .factory("BadgeDefs", function($http){

      var data = {}

      function load(){

        var url = "/api/badges"
        return $http.get(url).success(function(resp){

          // clear the data object
          for (var member in data) delete data[member];

          // put the response in the data object
          _.each(resp, function(v, k){
            data[k] = v
          })

        })
      }

      return {
        d: data,
        load: load
      }
    })