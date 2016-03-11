angular.module('person', [
])



    .factory("Person", function($http){

      var data = {}

      function load(orcidId){



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

      return {
        d: data,
        load: load
      }
    })